from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from models.approval import ApprovalLog, ApprovalRequest
from models.project import Project
from models.user import User

approval_bp = Blueprint('approval', __name__, url_prefix='/approvals')

# Valid state transitions
VALID_TRANSITIONS = {
    'Pending': ['Under Review', 'Escalated'],
    'Under Review': ['Approved', 'Rejected'],
    'Escalated': ['Under Review', 'Approved', 'Rejected'],
}


def calculate_risk_score(submitted_by, description, deadline):
    """Rule-based rejection risk predictor (0.0 – 1.0)."""
    score = 0.0
    # Prior rejections for this submitter
    prior_rejections = ApprovalRequest.query.filter_by(
        submitted_by=submitted_by, status='Rejected'
    ).count()
    score += min(prior_rejections * 0.2, 0.6)
    # Deadline already past
    if deadline and datetime.utcnow() > deadline:
        score += 0.2
    # Thin description
    if not description or len(description.strip()) < 50:
        score += 0.2
    return round(min(score, 1.0), 2)


def auto_escalate():
    """Escalate overdue Pending / Under Review requests. Returns count escalated."""
    overdue = ApprovalRequest.query.filter(
        ApprovalRequest.status.in_(['Pending', 'Under Review']),
        ApprovalRequest.deadline.isnot(None),
        ApprovalRequest.deadline < datetime.utcnow(),
    ).all()
    for ar in overdue:
        old = ar.status
        ar.status = 'Escalated'
        ar.updated_at = datetime.utcnow()
        db.session.add(ApprovalLog(
            approval_id=ar.id,
            action='Auto-escalated — deadline expired',
            from_status=old,
            to_status='Escalated',
        ))
    if overdue:
        db.session.commit()
    return len(overdue)


# ─── Dashboard ──────────────────────────────────────────────────────────────

@approval_bp.route('/')
@jwt_required()
def dashboard():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user.role == 'Owner':
        return redirect(url_for('owner.owner_home'))

    n_escalated = auto_escalate()
    if n_escalated:
        flash(f'{n_escalated} request(s) auto-escalated due to expired deadline.', 'warning')

    total = ApprovalRequest.query.count()
    pending = ApprovalRequest.query.filter_by(status='Pending').count()
    under_review = ApprovalRequest.query.filter_by(status='Under Review').count()
    approved = ApprovalRequest.query.filter_by(status='Approved').count()
    rejected = ApprovalRequest.query.filter_by(status='Rejected').count()
    escalated = ApprovalRequest.query.filter_by(status='Escalated').count()

    recent = ApprovalRequest.query.order_by(
        ApprovalRequest.updated_at.desc()
    ).limit(8).all()

    high_risk = ApprovalRequest.query.filter(
        ApprovalRequest.risk_score >= 0.6,
        ApprovalRequest.status.in_(['Pending', 'Under Review', 'Escalated']),
    ).order_by(ApprovalRequest.risk_score.desc()).limit(5).all()

    return render_template(
        'approval_dashboard.html',
        user=user,
        total=total, pending=pending, under_review=under_review,
        approved=approved, rejected=rejected, escalated=escalated,
        recent=recent, high_risk=high_risk,
    )


# ─── Queue ───────────────────────────────────────────────────────────────────

@approval_bp.route('/queue')
@jwt_required()
def queue():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user.role == 'Owner':
        return redirect(url_for('owner.owner_home'))
    auto_escalate()

    status_filter = request.args.get('status', '')
    q = ApprovalRequest.query.order_by(ApprovalRequest.created_at.desc())
    if status_filter:
        q = q.filter_by(status=status_filter)
    requests_list = q.all()
    projects = Project.query.order_by(Project.name).all()

    counts = {
        'All': ApprovalRequest.query.count(),
        'Pending': ApprovalRequest.query.filter_by(status='Pending').count(),
        'Under Review': ApprovalRequest.query.filter_by(status='Under Review').count(),
        'Approved': ApprovalRequest.query.filter_by(status='Approved').count(),
        'Rejected': ApprovalRequest.query.filter_by(status='Rejected').count(),
        'Escalated': ApprovalRequest.query.filter_by(status='Escalated').count(),
    }

    return render_template(
        'approval_queue.html',
        user=user,
        requests_list=requests_list,
        projects=projects,
        status_filter=status_filter,
        counts=counts,
        valid_transitions=VALID_TRANSITIONS,
    )


# ─── Submit ──────────────────────────────────────────────────────────────────

@approval_bp.route('/submit', methods=['POST'])
@jwt_required()
def submit():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    project_id = request.form.get('project_id', type=int)
    deadline_str = request.form.get('deadline', '').strip()

    if not title:
        flash('Title is required.', 'error')
        return redirect(url_for('approval.queue'))

    deadline = None
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
        except ValueError:
            pass

    risk = calculate_risk_score(user.username, description, deadline)

    ar = ApprovalRequest(
        title=title,
        description=description,
        project_id=project_id or None,
        submitted_by=user.username,
        status='Pending',
        risk_score=risk,
        deadline=deadline,
    )
    db.session.add(ar)
    db.session.flush()
    db.session.add(ApprovalLog(
        approval_id=ar.id,
        action='Request submitted',
        performed_by=user.username,
        from_status=None,
        to_status='Pending',
    ))
    db.session.commit()
    flash('Approval request submitted successfully.', 'success')
    return redirect(url_for('approval.queue'))


# ─── Transition ──────────────────────────────────────────────────────────────

@approval_bp.route('/<int:ar_id>/transition', methods=['POST'])
@jwt_required()
def transition(ar_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    ar = ApprovalRequest.query.get_or_404(ar_id)
    new_status = request.form.get('status', '').strip()
    notes = request.form.get('notes', '').strip()
    rejection_reason = request.form.get('rejection_reason', '').strip()

    # Only Authority can approve or reject
    if new_status in ('Approved', 'Rejected') and user.role != 'Authority':
        flash('Only Authority users can approve or reject requests.', 'error')
        return redirect(url_for('approval.queue'))

    allowed = VALID_TRANSITIONS.get(ar.status, [])
    if new_status not in allowed:
        flash(f'Cannot transition from "{ar.status}" to "{new_status}".', 'error')
        return redirect(url_for('approval.queue'))

    old_status = ar.status
    ar.status = new_status
    ar.reviewed_by = user.username
    ar.review_notes = notes
    ar.updated_at = datetime.utcnow()
    if new_status == 'Rejected':
        ar.rejection_reason = rejection_reason

    db.session.add(ApprovalLog(
        approval_id=ar.id,
        action=f'Status changed to {new_status}',
        performed_by=user.username,
        notes=notes or rejection_reason or None,
        from_status=old_status,
        to_status=new_status,
    ))
    db.session.commit()
    flash(f'Request marked as {new_status}.', 'success')
    return redirect(url_for('approval.queue'))


# ─── History ─────────────────────────────────────────────────────────────────

@approval_bp.route('/history')
@jwt_required()
def history():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user.role == 'Owner':
        return redirect(url_for('owner.owner_home'))
    logs = ApprovalLog.query.order_by(ApprovalLog.timestamp.desc()).limit(200).all()
    return render_template('approval_history.html', user=user, logs=logs)


# ─── Kanban ──────────────────────────────────────────────────────────────────

@approval_bp.route('/kanban')
@jwt_required()
def kanban():
    user = User.query.get(get_jwt_identity())
    if user.role == 'Owner':
        return redirect(url_for('owner.owner_home'))
    auto_escalate()

    columns = {
        'Pending': ApprovalRequest.query.filter_by(status='Pending').order_by(
            ApprovalRequest.deadline.asc()
        ).all(),
        'Under Review': ApprovalRequest.query.filter_by(status='Under Review').order_by(
            ApprovalRequest.risk_score.desc()
        ).all(),
        'Approved': ApprovalRequest.query.filter_by(status='Approved').order_by(
            ApprovalRequest.updated_at.desc()
        ).all(),
        'Rejected': ApprovalRequest.query.filter_by(status='Rejected').order_by(
            ApprovalRequest.updated_at.desc()
        ).all(),
        'Escalated': ApprovalRequest.query.filter_by(status='Escalated').order_by(
            ApprovalRequest.risk_score.desc()
        ).all(),
    }

    wip_limits = {
        'Pending': None,
        'Under Review': 5,
        'Approved': None,
        'Rejected': None,
        'Escalated': 3,
    }

    return render_template(
        'approval_kanban.html',
        columns=columns,
        wip_limits=wip_limits,
        user=user,
    )


@approval_bp.route('/<int:ar_id>/move', methods=['POST'])
@jwt_required()
def move_card(ar_id):
    """AJAX endpoint for kanban drag-and-drop."""
    user = User.query.get(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    new_status = data.get('status', '').strip()

    ar = ApprovalRequest.query.get_or_404(ar_id)
    old_status = ar.status

    allowed = VALID_TRANSITIONS.get(old_status, [])
    if new_status not in allowed:
        return jsonify({'error': f'Cannot move from {old_status} to {new_status}'}), 400

    ar.status = new_status
    ar.updated_at = datetime.utcnow()
    if new_status in ('Approved', 'Rejected'):
        ar.reviewed_by = user.username

    db.session.add(ApprovalLog(
        approval_id=ar_id,
        action='Moved via Kanban',
        performed_by=user.username,
        from_status=old_status,
        to_status=new_status,
        notes=f'Dragged from {old_status} to {new_status}',
    ))
    db.session.commit()
    return jsonify({'success': True, 'new_status': new_status}), 200
