import json
import os
import secrets
from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from models.mom import MeetingMinutes, MomItem
from models.project import Project
from models.user import User

mom_bp = Blueprint('mom', __name__)

VALID_STATES = {'Decided', 'Pending', 'Deferred'}


def _fetch_compliance_snapshot():
    """Pull latest compliance check from BuildIQ. Returns (score, status, snapshot_json)."""
    try:
        import requests as req
        base = os.getenv('BUILDIQ_URL', 'http://localhost:8000')
        r = req.post(f'{base}/api/demo-check', json={
            'road_width_ft': 20, 'provided_front_m': 3.0,
            'provided_rear_m': 1.5, 'provided_side_m': 1.5,
            'plot_area_sqm': 111, 'proposed_builtup_sqm': 167,
            'footprint_sqm': 72, 'proposed_height_m': 7.0,
            'floors': 2, 'zone_type': 'residential_R1',
            'building_type': 'residential',
            'proposed_spaces': 2, 'num_units': 2,
        }, timeout=5)
        if r.status_code == 200:
            d = r.json()
            results = d.get('results', {})
            scores = [
                v.get('confidence') or v.get('score', 0)
                for v in results.values() if isinstance(v, dict)
            ]
            comp_score = round(sum(scores) / len(scores), 3) if scores else None
            comp_status = d.get('overall_status', '')
            comp_snapshot = json.dumps({
                k: {
                    'confidence': v.get('confidence') or v.get('score', 0),
                    'status': v.get('status', ''),
                    'fix': v.get('fix_suggestion', '')
                }
                for k, v in results.items() if isinstance(v, dict)
            })
            return comp_score, comp_status, comp_snapshot
    except Exception:
        pass
    return None, None, None


def _check_lock(mom):
    if mom.creator_signed and mom.client_signed and not mom.is_locked:
        mom.is_locked = True
        mom.locked_at = datetime.utcnow()


# ── List all MoMs for a project ───────────────────────────────────────────────

@mom_bp.route('/mom/<int:project_id>')
@jwt_required()
def mom_list(project_id):
    user = User.query.get(get_jwt_identity())
    project = Project.query.get_or_404(project_id)
    moms = MeetingMinutes.query.filter_by(project_id=project_id)\
                               .order_by(MeetingMinutes.meeting_date.desc()).all()
    total  = len(moms)
    locked = sum(1 for m in moms if m.is_locked)
    pending_sig = sum(1 for m in moms if not m.is_locked)
    return render_template('mom_list.html', moms=moms, project=project, user=user,
                           total=total, locked=locked, pending_sig=pending_sig)


# ── Create new MoM ────────────────────────────────────────────────────────────

@mom_bp.route('/mom/<int:project_id>/create', methods=['GET', 'POST'])
@jwt_required()
def mom_create(project_id):
    uid = get_jwt_identity()
    user = User.query.get(uid)
    project = Project.query.get_or_404(project_id)

    if request.method == 'POST':
        title        = request.form.get('title', '').strip() or \
                       'Meeting — ' + datetime.utcnow().strftime('%d %b %Y')
        client_email = request.form.get('client_email', '').strip()

        comp_score, comp_status, comp_snapshot = _fetch_compliance_snapshot()

        mom = MeetingMinutes(
            project_id=project_id,
            title=title,
            client_email=client_email,
            created_by=uid,
            compliance_score=comp_score,
            compliance_status=comp_status,
            compliance_snapshot=comp_snapshot,
            share_token=secrets.token_urlsafe(32),
        )
        db.session.add(mom)
        db.session.flush()

        items_raw = request.form.getlist('items')
        states    = request.form.getlist('states')
        for i, text in enumerate(items_raw):
            text = text.strip()
            if not text:
                continue
            db.session.add(MomItem(
                mom_id=mom.id,
                text=text,
                state=states[i] if i < len(states) and states[i] in VALID_STATES else 'Pending',
                order=i,
                added_by=uid,
            ))
        db.session.commit()
        flash('Meeting minutes created.', 'success')
        return redirect(url_for('mom.mom_detail', mom_id=mom.id))

    today = datetime.utcnow().strftime('%Y-%m-%d')
    return render_template('mom_create.html', project=project, user=user, today=today)


# ── View / edit a MoM ─────────────────────────────────────────────────────────

@mom_bp.route('/mom/detail/<int:mom_id>', methods=['GET', 'POST'])
@jwt_required()
def mom_detail(mom_id):
    uid  = get_jwt_identity()
    user = User.query.get(uid)
    mom  = MeetingMinutes.query.get_or_404(mom_id)

    if request.method == 'POST' and not mom.is_locked:
        for item in mom.items:
            new_state = request.form.get(f'state_{item.id}')
            if new_state in VALID_STATES:
                item.state = new_state
            new_text = request.form.get(f'text_{item.id}', '').strip()
            if new_text:
                item.text = new_text

        new_items  = request.form.getlist('new_items')
        new_states = request.form.getlist('new_states')
        for i, text in enumerate(new_items):
            text = text.strip()
            if not text:
                continue
            db.session.add(MomItem(
                mom_id=mom_id,
                text=text,
                state=new_states[i] if i < len(new_states) and new_states[i] in VALID_STATES else 'Pending',
                order=len(mom.items) + i,
                added_by=uid,
            ))
        db.session.commit()
        flash('Minutes updated.', 'success')

    snapshot = None
    if mom.compliance_snapshot:
        try:
            snapshot = json.loads(mom.compliance_snapshot)
        except Exception:
            pass

    share_url = url_for('mom.mom_client_sign', token=mom.share_token, _external=True) \
                if mom.share_token else None

    return render_template('mom_detail.html', mom=mom, snapshot=snapshot,
                           user=user, share_url=share_url,
                           is_creator=(str(mom.created_by) == str(uid)))


# ── Creator signs ─────────────────────────────────────────────────────────────

@mom_bp.route('/mom/sign/<int:mom_id>', methods=['POST'])
@jwt_required()
def mom_sign(mom_id):
    uid = get_jwt_identity()
    mom = MeetingMinutes.query.get_or_404(mom_id)
    if str(mom.created_by) == str(uid) and not mom.creator_signed:
        mom.creator_signed    = True
        mom.creator_signed_at = datetime.utcnow()
        _check_lock(mom)
        db.session.commit()
        flash('You have signed these minutes.', 'success')
    return redirect(url_for('mom.mom_detail', mom_id=mom_id))


# ── Client signs via share link (no auth required) ────────────────────────────

@mom_bp.route('/mom/client-sign/<token>', methods=['GET', 'POST'])
def mom_client_sign(token):
    mom = MeetingMinutes.query.filter_by(share_token=token).first_or_404()
    if request.method == 'POST' and not mom.client_signed and not mom.is_locked:
        mom.client_signed    = True
        mom.client_signed_at = datetime.utcnow()
        _check_lock(mom)
        db.session.commit()
        return render_template('mom_signed.html', mom=mom)
    return render_template('mom_client_sign.html', mom=mom)
