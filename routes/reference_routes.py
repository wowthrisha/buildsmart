import os

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.utils import secure_filename

from extensions import db
from models.project import Project
from models.reference_board import DESIGN_TAGS, ReferencePin
from models.user import User

ref_bp = Blueprint('ref', __name__)


# ── Redirect /board → first project ──────────────────────────────────────────

@ref_bp.route('/board')
@jwt_required()
def board_home():
    from models.project import Project
    from models.user import User
    uid  = get_jwt_identity()
    user = User.query.get(uid)
    if user and user.role == 'Owner':
        project = Project.query.filter_by(owner_id=uid).first()
    else:
        project = Project.query.filter_by(architect_id=uid).order_by(Project.created_at).first()
        if not project:
            project = Project.query.first()
    if project:
        return redirect(url_for('ref.board', project_id=project.id))
    return redirect(url_for('document.dashboard'))


# ── Board view ────────────────────────────────────────────────────────────────

@ref_bp.route('/board/<int:project_id>')
@jwt_required()
def board(project_id):
    user       = User.query.get(get_jwt_identity())
    project    = Project.query.get_or_404(project_id)
    tag_filter = request.args.get('tag', '')

    query = ReferencePin.query.filter_by(project_id=project_id)
    if tag_filter:
        query = query.filter(ReferencePin.design_tags.contains(tag_filter))
    pins = query.order_by(ReferencePin.created_at.desc()).all()

    tagged = {}
    for pin in pins:
        tags = [t.strip() for t in (pin.design_tags or '').split(',') if t.strip()]
        for tag in tags:
            tagged.setdefault(tag, []).append(pin)

    return render_template('reference_board.html',
                           pins=pins, tagged=tagged,
                           project=project, user=user,
                           all_tags=DESIGN_TAGS,
                           active_tag=tag_filter)


# ── Add pin via URL ───────────────────────────────────────────────────────────

@ref_bp.route('/board/<int:project_id>/add-url', methods=['POST'])
@jwt_required()
def add_url(project_id):
    uid = get_jwt_identity()
    url = request.form.get('url', '').strip()
    if not url:
        return redirect(url_for('ref.board', project_id=project_id))

    image_url = None
    title     = url[:100]
    site_name = ''

    try:
        import requests as req
        from html.parser import HTMLParser

        class OGParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.og = {}
            def handle_starttag(self, tag, attrs):
                if tag == 'meta':
                    d = dict(attrs)
                    prop = d.get('property', '') or d.get('name', '')
                    if prop in ('og:image', 'og:title', 'og:site_name'):
                        self.og[prop] = d.get('content', '')

        r = req.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        parser = OGParser()
        parser.feed(r.text[:50000])
        image_url = parser.og.get('og:image', '')
        title     = parser.og.get('og:title', url[:100])
        site_name = parser.og.get('og:site_name', '')

        if 'pinterest' in url:    site_name = 'Pinterest'
        elif 'instagram' in url:  site_name = 'Instagram'
        elif 'houzz' in url:      site_name = 'Houzz'
        elif 'archdaily' in url:  site_name = 'ArchDaily'
    except Exception:
        pass

    pin = ReferencePin(
        project_id=project_id,
        added_by=uid,
        source_url=url,
        image_url=image_url or None,
        title=title,
        site_name=site_name,
    )
    db.session.add(pin)
    db.session.commit()
    return redirect(url_for('ref.board', project_id=project_id))


# ── Add pin via image upload ──────────────────────────────────────────────────

@ref_bp.route('/board/<int:project_id>/add-image', methods=['POST'])
@jwt_required()
def add_image(project_id):
    uid  = get_jwt_identity()
    file = request.files.get('image')
    if not file or not file.filename:
        return redirect(url_for('ref.board', project_id=project_id))

    upload_dir = 'uploads/pins'
    os.makedirs(upload_dir, exist_ok=True)
    filename = secure_filename(file.filename)
    path = os.path.join(upload_dir, filename)
    file.save(path)

    pin = ReferencePin(
        project_id=project_id,
        added_by=uid,
        local_image=path,
        title=filename,
        site_name='Uploaded',
    )
    db.session.add(pin)
    db.session.commit()
    return redirect(url_for('ref.board', project_id=project_id))


# ── Update tags + note (AJAX) ─────────────────────────────────────────────────

@ref_bp.route('/board/pin/<int:pin_id>/update', methods=['POST'])
@jwt_required()
def update_pin(pin_id):
    pin      = ReferencePin.query.get_or_404(pin_id)
    data     = request.get_json(silent=True) or {}
    tags     = data.get('tags', [])
    note     = data.get('note', '')
    mom_item = data.get('mom_item_id')

    pin.design_tags = ','.join(tags)
    pin.arch_note   = note
    if mom_item:
        pin.mom_item_id = int(mom_item)
    db.session.commit()
    return jsonify({'success': True})


# ── Delete a pin ──────────────────────────────────────────────────────────────

@ref_bp.route('/board/pin/<int:pin_id>/delete', methods=['POST'])
@jwt_required()
def delete_pin(pin_id):
    pin        = ReferencePin.query.get_or_404(pin_id)
    project_id = pin.project_id
    db.session.delete(pin)
    db.session.commit()
    return redirect(url_for('ref.board', project_id=project_id))
