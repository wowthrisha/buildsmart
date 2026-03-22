from dotenv import load_dotenv
load_dotenv()

from flask import Flask, make_response, redirect, url_for
from config import Config
from extensions import db
from flask_jwt_extended import JWTManager
import models
from flask_migrate import Migrate


def create_app():
    
    app = Flask(__name__)
    app.config.from_object(Config)


    db.init_app(app)
    Migrate(app, db) 

    jwt = JWTManager(app)

    @jwt.unauthorized_loader
    def unauthorized_callback(callback):
        return redirect(url_for("auth.login"))

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return redirect(url_for("auth.login"))

    @app.before_request
    def check_user_exists():
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
        from flask import request
        from models.user import User
        # skip static files and auth routes
        if request.endpoint and (
            request.endpoint.startswith("auth.") or
            request.endpoint == "static" or
            request.endpoint.startswith("public") or
            request.endpoint == "mom.mom_client_sign"
        ):
            return
        try:
            verify_jwt_in_request(optional=True)
            uid = get_jwt_identity()
            if uid and User.query.get(uid) is None:
                resp = make_response(redirect(url_for("auth.login")))
                resp.delete_cookie("access_token_cookie")
                return resp
        except Exception:
            pass

    # register routes
    from routes.document_routes import document_bp
    from routes.auth_routes import auth_bp
    from routes.timeline_routes import timeline_bp
    from routes.compliance_routes import compliance_bp
    from routes.owner_routes import owner_bp
    from routes.approval_routes import approval_bp
    from routes.mom_routes import mom_bp
    from routes.reference_routes import ref_bp

    app.register_blueprint(document_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(timeline_bp)
    app.register_blueprint(compliance_bp)
    app.register_blueprint(owner_bp)
    app.register_blueprint(approval_bp)
    app.register_blueprint(mom_bp)
    app.register_blueprint(ref_bp)

    @app.context_processor
    def inject_user_role():
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
        from models.user import User
        try:
            verify_jwt_in_request(optional=True)
            uid = get_jwt_identity()
            if uid:
                user = User.query.get(uid)
                return {'current_user_role': user.role if user else ''}
        except Exception:
            pass
        return {'current_user_role': ''}

    @app.context_processor
    def inject_projects():
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
        from models.project import Project
        from models.user import User
        try:
            verify_jwt_in_request(optional=True)
            uid = get_jwt_identity()
            if uid:
                user = User.query.get(uid)
                if user and user.role == 'Owner':
                    # Owner sees only their assigned project(s)
                    projects = Project.query.filter_by(owner_id=uid).order_by(Project.created_at.desc()).all()
                else:
                    # Architect sees projects they manage
                    projects = Project.query.filter_by(architect_id=uid).order_by(Project.created_at.desc()).limit(10).all()
                    if not projects:
                        # Fallback: unassigned projects (for existing data before migration)
                        projects = Project.query.filter_by(architect_id=None).order_by(Project.created_at.desc()).limit(10).all()
                return {'get_all_projects': lambda: projects, 'active_project_id': None}
        except Exception:
            pass
        return {'get_all_projects': lambda: [], 'active_project_id': None}

    with app.app_context():
        from models.compliance_models import ComplianceRequirement
        from models.mom import MeetingMinutes, MomItem
        from models.reference_board import ReferencePin
        db.create_all()
        _migrate_columns(app)
        _seed_demo_users(app)
        _seed_demo_data(app)

    return app


def _migrate_columns(app):
    """Add new columns to existing SQLite tables without dropping data."""
    with app.app_context():
        conn = db.engine.raw_connection()
        cur  = conn.cursor()
        for col, typedef in [
            ('architect_id', 'INTEGER REFERENCES users(id)'),
            ('owner_id',     'INTEGER REFERENCES users(id)'),
        ]:
            try:
                cur.execute(f'ALTER TABLE projects ADD COLUMN {col} {typedef}')
                conn.commit()
                print(f'Migrated: projects.{col} added')
            except Exception:
                pass  # column already exists
        conn.close()


def _seed_demo_users(app):
    """Ensure demo accounts exist with known passwords. Safe to call repeatedly."""
    from models.user import User
    from werkzeug.security import generate_password_hash
    demos = [
        {'username': 'arch_demo',  'email': 'arch@test.com',  'role': 'Architect'},
        {'username': 'owner_demo', 'email': 'owner@test.com', 'role': 'Owner'},
        {'username': 'eng_demo',   'email': 'eng@test.com',   'role': 'Architect'},
        {'username': 'auth_demo',  'email': 'auth@test.com',  'role': 'Owner'},
    ]
    with app.app_context():
        for d in demos:
            user = User.query.filter_by(email=d['email']).first()
            if user is None:
                user = User(username=d['username'], email=d['email'], role=d['role'])
                db.session.add(user)
            # Always reset password so demo creds are reliable
            user.password_hash = generate_password_hash('test123')
        db.session.commit()


def _seed_demo_data(app):
    """
    Seed rich demo data for every feature. Each section is independently
    guarded so it is safe to call on restarts even with an existing DB.
    """
    from models.project import Project, TimelineEvent
    from models.approval import ApprovalRequest, ApprovalLog
    from models.compliance_models import ComplianceRequirement, REQUIRED_DOCUMENT_TYPES
    from models.mom import MeetingMinutes, MomItem
    from models.reference_board import ReferencePin
    from models.user import User
    import secrets
    from datetime import datetime, timedelta

    now = datetime.utcnow

    with app.app_context():
        arch  = User.query.filter_by(email='arch@test.com').first()
        owner = User.query.filter_by(email='owner@test.com').first()
        auth  = User.query.filter_by(email='auth@test.com').first()
        if not arch:
            return

        # ── 1. Projects ────────────────────────────────────────────────────────
        if Project.query.count() == 0:
            projects_data = [
                ('Coimbatore Residential — Plot 42',
                 'G+1 residential, 30x40ft, CCMC zone, Dr. Suresh',
                 arch, owner),
                ('Chennai Commercial — Anna Nagar Block C',
                 'G+3 commercial, 50x60ft, CMC zone, Mr. Rajesh',
                 arch, auth),
                ('Madurai Villa — Surveyor Colony',
                 'Single-storey villa, 40x50ft, MCC zone, Dr. Rajan',
                 arch, None),
            ]
            projects = []
            for name, desc, arc, own in projects_data:
                p = Project(
                    name=name, description=desc,
                    architect_id=arc.id if arc else None,
                    owner_id=own.id if own else None,
                )
                db.session.add(p)
                projects.append(p)
            db.session.flush()
        else:
            projects = Project.query.order_by(Project.created_at).all()
            # Backfill architect/owner onto existing projects if unset
            for i, (arc, own) in enumerate([(arch, owner), (arch, auth), (arch, None)]):
                if i < len(projects):
                    p = projects[i]
                    if p.architect_id is None and arc:
                        p.architect_id = arc.id
                    if p.owner_id is None and own:
                        p.owner_id = own.id

        p1 = projects[0]
        p2 = projects[1] if len(projects) > 1 else p1
        p3 = projects[2] if len(projects) > 2 else p1

        # ── 2. Timeline events ─────────────────────────────────────────────────
        if TimelineEvent.query.count() == 0:
            timeline_rows = [
                (p1.id, 'Project Created',        'Project initiated by architect',                  12),
                (p1.id, 'Document Uploaded',       'FMB sketch uploaded v1',                         10),
                (p1.id, 'Compliance Check Completed','AI compliance score: 78% — marginal setback',   8),
                (p1.id, 'Submitted for Approval',  'Application submitted to CCMC portal',            6),
                (p1.id, 'Authority Review',        'CCMC officer raised setback query',               4),
                (p2.id, 'Project Created',         'Commercial project initiated',                   14),
                (p2.id, 'Document Uploaded',       'Structural drawings uploaded',                   11),
                (p2.id, 'Compliance Check Completed','FAR check passed at 1.6 (limit 1.75)',          9),
                (p3.id, 'Project Created',         'Villa project registered',                       20),
                (p3.id, 'Document Uploaded',       'Site plan & FMB uploaded',                       18),
            ]
            for pid, etype, desc, days_ago in timeline_rows:
                db.session.add(TimelineEvent(
                    project_id=pid, event_type=etype, description=desc,
                    created_at=now() - timedelta(days=days_ago)
                ))

        # ── 3. Approval requests — one per Kanban column ───────────────────────
        if ApprovalRequest.query.count() == 0:
            approvals = [
                # (title, description, status, risk, project, days_deadline, reviewed_by, notes)
                ('Site plan — Plot 42',
                 'Site plan at 1:500 scale showing all setbacks and abutting road widths.',
                 'Pending', 0.20, p1.id, 5, None, None),
                ('FMB sketch verification — Plot 42',
                 'Field Measurement Book sketch must match registered patta boundaries.',
                 'Pending', 0.55, p1.id, 3, None, None),
                ('Structural drawing review — Anna Nagar',
                 'RCC column layout and foundation depth for G+3 load.',
                 'Under Review', 0.35, p2.id, 7, 'arch_demo', 'Awaiting engineer sign-off'),
                ('Fire NOC — Anna Nagar commercial',
                 'NOC from Tamil Nadu Fire & Rescue Services for commercial occupancy.',
                 'Under Review', 0.70, p2.id, 2, 'arch_demo', 'High risk — deadline close'),
                ('Setback compliance — Plot 42',
                 'Front setback revised to 3.5m as per CCMC directive. All sides verified.',
                 'Approved', 0.10, p1.id, -5, 'auth_demo', 'All measurements confirmed on-site'),
                ('Patta ownership document',
                 'Original patta and chitta submitted and verified by revenue office.',
                 'Approved', 0.05, p3.id, -10, 'auth_demo', 'Clear title — no encumbrance'),
                ('Height clearance — Anna Nagar',
                 'Proposed height 13.2m; AAI clearance needed for proximity to airport zone.',
                 'Rejected', 0.80, p2.id, -3, 'auth_demo', 'AAI objection — reduce height below 12m'),
                ('EC document — Plot 42',
                 'Encumbrance Certificate covering last 30 years as required by CCMC.',
                 'Escalated', 0.65, p1.id, -2, None, 'Auto-escalated — deadline expired'),
            ]
            for title, desc, status, risk, pid, ddays, rev_by, notes in approvals:
                ar = ApprovalRequest(
                    title=title,
                    description=desc,
                    status=status,
                    risk_score=risk,
                    project_id=pid,
                    submitted_by=arch.username,
                    reviewed_by=rev_by,
                    review_notes=notes,
                    deadline=now() + timedelta(days=ddays),
                    created_at=now() - timedelta(days=abs(ddays) + 3),
                    updated_at=now() - timedelta(days=1),
                )
                if status == 'Rejected':
                    ar.rejection_reason = notes
                db.session.add(ar)
                db.session.flush()
                db.session.add(ApprovalLog(
                    approval_id=ar.id,
                    action='Request submitted',
                    performed_by=arch.username,
                    from_status=None,
                    to_status='Pending',
                    timestamp=now() - timedelta(days=abs(ddays) + 3),
                ))
                if status not in ('Pending',):
                    db.session.add(ApprovalLog(
                        approval_id=ar.id,
                        action=f'Status changed to {status}',
                        performed_by=rev_by or 'system',
                        notes=notes,
                        from_status='Pending',
                        to_status=status,
                        timestamp=now() - timedelta(days=1),
                    ))

        # ── 4. Compliance requirements ─────────────────────────────────────────
        if ComplianceRequirement.query.count() == 0:
            for pid in [p1.id, p2.id]:
                for doc_type in REQUIRED_DOCUMENT_TYPES:
                    db.session.add(ComplianceRequirement(
                        project_id=pid, document_type=doc_type,
                    ))

        # ── 5. Meeting Minutes ─────────────────────────────────────────────────
        if MeetingMinutes.query.count() == 0:
            moms = [
                dict(
                    project_id=p1.id,
                    title='Design Review Meeting — 15 Mar 2026',
                    created_by=arch.id,
                    compliance_score=0.78,
                    compliance_status='MARGINAL',
                    compliance_snapshot='{"setback":{"confidence":0.65,"status":"MARGINAL","fix":"Increase front setback to 3.5m"},'
                                        '"far":{"confidence":0.90,"status":"PASS","fix":""},'
                                        '"coverage":{"confidence":0.82,"status":"PASS","fix":""}}',
                    share_token=secrets.token_urlsafe(32),
                    creator_signed=True,
                    creator_signed_at=now() - timedelta(days=1),
                    meeting_date=now() - timedelta(days=1),
                ),
                dict(
                    project_id=p2.id,
                    title='Pre-submission Client Meeting — 10 Mar 2026',
                    created_by=arch.id,
                    compliance_score=0.91,
                    compliance_status='PASS',
                    compliance_snapshot='{"setback":{"confidence":0.95,"status":"PASS","fix":""},'
                                        '"far":{"confidence":0.88,"status":"PASS","fix":""},'
                                        '"height":{"confidence":0.90,"status":"PASS","fix":""}}',
                    share_token=secrets.token_urlsafe(32),
                    creator_signed=False,
                    meeting_date=now() - timedelta(days=7),
                ),
            ]
            mom_items = [
                [
                    ('Increase front setback to 3.5m before resubmission', 'Decided'),
                    ('Submit updated FMB sketch by 22 March',               'Decided'),
                    ('Confirm parking space count with owner',              'Pending'),
                    ('Check with CCMC on road width classification',        'Deferred'),
                ],
                [
                    ('Client to provide updated patta copy',                'Decided'),
                    ('Structural engineer to submit revised RCC layout',    'Pending'),
                    ('Fire NOC application to be filed by 25 March',        'Decided'),
                    ('Review AAI height restriction for Anna Nagar zone',   'Pending'),
                ],
            ]
            for mom_data, items in zip(moms, mom_items):
                m = MeetingMinutes(**mom_data)
                db.session.add(m)
                db.session.flush()
                for i, (text, state) in enumerate(items):
                    db.session.add(MomItem(
                        mom_id=m.id, text=text, state=state,
                        order=i, added_by=arch.id
                    ))

        # ── 6. Reference board pins ────────────────────────────────────────────
        if ReferencePin.query.count() == 0:
            pins = [
                dict(project_id=p1.id, added_by=arch.id,
                     source_url='https://www.pinterest.com/pin/courtyard-house-design',
                     image_url='https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=600',
                     title='Courtyard House — Vastu-compliant layout', site_name='Pinterest',
                     design_tags='courtyard,vastu,natural-light',
                     arch_note='Good reference for central courtyard placement in G+1 residential.'),
                dict(project_id=p1.id, added_by=arch.id,
                     source_url='https://www.archdaily.com/setback-design-tropical',
                     image_url='https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600',
                     title='Tropical setback design — TNCDBR compliant', site_name='ArchDaily',
                     design_tags='setback,tropical,ventilation',
                     arch_note='Front setback 3.5m matches CCMC requirement; side openings improve cross-ventilation.'),
                dict(project_id=p1.id, added_by=arch.id,
                     source_url='https://www.houzz.com/photos/compact-parking-layout',
                     image_url='https://images.unsplash.com/photo-1486325212027-8081e485255e?w=600',
                     title='Compact 2-car parking within plot', site_name='Houzz',
                     design_tags='parking,compact,layout',
                     arch_note='Fits 2 spaces in 2.5×5m each — meets R1 zone parking norm.'),
                dict(project_id=p1.id, added_by=arch.id,
                     source_url='https://www.archdaily.com/low-cost-rcc-slab',
                     image_url='https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=600',
                     title='Low-cost RCC slab for G+1', site_name='ArchDaily',
                     design_tags='structure,rcc,cost',
                     arch_note='230mm slab with M20 concrete; suitable for 7m height cap.'),
                dict(project_id=p2.id, added_by=arch.id,
                     source_url='https://www.archdaily.com/commercial-facade-chennai',
                     image_url='https://images.unsplash.com/photo-1486006920555-c77dcf18193c?w=600',
                     title='Commercial facade — Anna Nagar style', site_name='ArchDaily',
                     design_tags='commercial,facade,glazing',
                     arch_note='Double-glazed curtain wall reduces heat load in Chennai climate.'),
            ]
            for pin_data in pins:
                db.session.add(ReferencePin(**pin_data))

        try:
            db.session.commit()
            print('Demo data seeded successfully')
        except Exception as e:
            db.session.rollback()
            print(f'Demo seed failed: {e}')


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5001)

