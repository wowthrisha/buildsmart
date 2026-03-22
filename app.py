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
        try:
            verify_jwt_in_request(optional=True)
            uid = get_jwt_identity()
            if uid:
                projects = Project.query.order_by(Project.created_at.desc()).limit(5).all()
                return {'get_all_projects': lambda: projects, 'active_project_id': None}
        except Exception:
            pass
        return {'get_all_projects': lambda: [], 'active_project_id': None}

    with app.app_context():
        from models.compliance_models import ComplianceRequirement
        from models.mom import MeetingMinutes, MomItem
        from models.reference_board import ReferencePin
        db.create_all()
        _seed_demo_users(app)
        _seed_demo_data(app)

    return app


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
    """Seed a demo project with timeline, approvals, compliance, and MoM. Idempotent."""
    from models.project import Project, TimelineEvent
    from models.approval import ApprovalRequest
    from models.compliance_models import ComplianceRequirement, REQUIRED_DOCUMENT_TYPES
    from models.mom import MeetingMinutes, MomItem
    from models.user import User
    import secrets
    from datetime import datetime, timedelta

    with app.app_context():
        if Project.query.count() > 0:
            return

        arch = User.query.filter_by(email='arch@test.com').first()
        if not arch:
            return

        p = Project(
            name='Coimbatore Residential — Plot 42',
            description='G+1 residential, 30x40ft, CCMC zone, Dr. Suresh',
        )
        db.session.add(p)
        db.session.flush()

        stages = [
            ('Project Created',       'Project initiated by architect'),
            ('Document Uploaded',     'FMB sketch uploaded v1'),
            ('Compliance Check Run',  'AI compliance score: 78%'),
            ('Submitted for Approval','Application submitted to CCMC'),
        ]
        for i, (etype, desc) in enumerate(stages):
            db.session.add(TimelineEvent(
                project_id=p.id,
                event_type=etype,
                description=desc,
                created_at=datetime.utcnow() - timedelta(days=10 - i * 2)
            ))

        approvals = [
            ('Site plan approval',      'Pending',       0.25),
            ('FMB sketch review',       'Under Review',  0.40),
            ('Setback compliance check','Approved',      0.15),
            ('EC document review',      'Pending',       0.60),
        ]
        for title, status, risk in approvals:
            db.session.add(ApprovalRequest(
                title=title,
                status=status,
                risk_score=risk,
                project_id=p.id,
                submitted_by=arch.username,
                deadline=datetime.utcnow() + timedelta(days=7)
            ))

        for doc_type in REQUIRED_DOCUMENT_TYPES:
            db.session.add(ComplianceRequirement(
                project_id=p.id,
                document_type=doc_type,
            ))

        mom = MeetingMinutes(
            project_id=p.id,
            title='Design Review Meeting — 15 Mar 2026',
            created_by=arch.id,
            compliance_score=0.78,
            compliance_status='MARGINAL',
            compliance_snapshot='{"setback":{"confidence":0.65,"status":"MARGINAL"},'
                                '"far":{"confidence":0.90,"status":"PASS"},'
                                '"coverage":{"confidence":0.82,"status":"PASS"}}',
            share_token=secrets.token_urlsafe(32),
            creator_signed=True,
            creator_signed_at=datetime.utcnow() - timedelta(days=1),
            meeting_date=datetime.utcnow() - timedelta(days=1),
        )
        db.session.add(mom)
        db.session.flush()

        for i, (text, state) in enumerate([
            ('Increase front setback to 3.5m before resubmission', 'Decided'),
            ('Submit updated FMB sketch by 22 March',              'Decided'),
            ('Confirm parking space count with owner',             'Pending'),
            ('Check with CCMC on road width classification',       'Deferred'),
        ]):
            db.session.add(MomItem(
                mom_id=mom.id, text=text, state=state,
                order=i, added_by=arch.id
            ))

        from models.reference_board import ReferencePin
        pins = [
            dict(
                project_id=p.id,
                added_by=arch.id,
                source_url='https://www.pinterest.com/pin/courtyard-house-design',
                image_url='https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=600',
                title='Courtyard House — Vastu-compliant layout',
                site_name='Pinterest',
                design_tags='courtyard,vastu,natural-light',
                arch_note='Good reference for central courtyard placement in G+1 residential.',
            ),
            dict(
                project_id=p.id,
                added_by=arch.id,
                source_url='https://www.archdaily.com/setback-design-tropical',
                image_url='https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600',
                title='Tropical setback design — TNCDBR compliant',
                site_name='ArchDaily',
                design_tags='setback,tropical,ventilation',
                arch_note='Front setback 3.5m matches CCMC requirement; side openings improve cross-ventilation.',
            ),
            dict(
                project_id=p.id,
                added_by=arch.id,
                source_url='https://www.houzz.com/photos/compact-parking-layout',
                image_url='https://images.unsplash.com/photo-1486325212027-8081e485255e?w=600',
                title='Compact 2-car parking within plot',
                site_name='Houzz',
                design_tags='parking,compact,layout',
                arch_note='Fits 2 spaces in 2.5×5m each — meets R1 zone parking norm.',
            ),
            dict(
                project_id=p.id,
                added_by=arch.id,
                source_url='https://www.archdaily.com/low-cost-rcc-slab',
                image_url='https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=600',
                title='Low-cost RCC slab for G+1',
                site_name='ArchDaily',
                design_tags='structure,rcc,cost',
                arch_note='230mm slab with M20 concrete; suitable for 7m height cap.',
            ),
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

