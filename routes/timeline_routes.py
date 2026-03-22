from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from models.project import Project, TimelineEvent
from models.user import User


timeline_bp = Blueprint("timeline", __name__)

PROGRESS_STAGES = [
    "Draft",
    "Compliance",
    "Submitted",
    "Authority Review",
    "Approved",
]

EVENT_STAGE_MAP = {
    "Project Created": "Draft",
    "Document Uploaded": "Compliance",
    "Compliance Check Completed": "Compliance",
    "Submitted for Approval": "Submitted",
    "Authority Review": "Authority Review",
    "Approval Granted": "Approved",
    "Approval Rejected": "Authority Review",
}


def get_project_stage(events):
    stage = "Draft"
    latest_rejection = None

    for event in sorted(events, key=lambda item: item.created_at):
        mapped_stage = EVENT_STAGE_MAP.get(event.event_type)
        if mapped_stage:
            stage = mapped_stage
        if event.event_type == "Approval Rejected":
            latest_rejection = event

    return stage, latest_rejection


@timeline_bp.route("/timeline/projects")
@jwt_required()
def projects():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user.role == "Owner":
        return redirect(url_for("owner.owner_home"))
    projects = Project.query.order_by(Project.created_at.desc()).all()

    project_summaries = []
    for project in projects:
        events = TimelineEvent.query.filter_by(project_id=project.id).order_by(TimelineEvent.created_at.desc()).all()
        current_stage, latest_rejection = get_project_stage(events)
        stage_index = PROGRESS_STAGES.index(current_stage) if current_stage in PROGRESS_STAGES else 0
        progress_percent = int((stage_index / (len(PROGRESS_STAGES) - 1)) * 100) if len(PROGRESS_STAGES) > 1 else 0
        project_summaries.append(
            {
                "project": project,
                "events": events,
                "current_stage": current_stage,
                "latest_rejection": latest_rejection,
                "progress_percent": progress_percent,
            }
        )

    return render_template(
        "timeline_projects.html",
        project_summaries=project_summaries,
        progress_stages=PROGRESS_STAGES,
        user=user,
    )


@timeline_bp.route("/timeline/create_project", methods=["POST"])
@jwt_required()
def create_project():
    user = User.query.get(get_jwt_identity())
    if user.role == "Owner":
        return redirect(url_for("owner.owner_home"))
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if not name:
        flash("Project name is required.", "error")
        return redirect(url_for("timeline.projects"))

    project = Project(name=name, description=description)
    db.session.add(project)
    db.session.flush()

    db.session.add(
        TimelineEvent(
            project_id=project.id,
            event_type="Project Created",
            description=description or "Project timeline initialized.",
        )
    )
    db.session.commit()

    flash("Project created successfully.", "success")
    return redirect(url_for("timeline.timeline", project_id=project.id))


@timeline_bp.route("/timeline/<int:project_id>")
@jwt_required()
def timeline(project_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user.role == "Owner":
        return redirect(url_for("owner.owner_home"))
    project = Project.query.get_or_404(project_id)
    events = TimelineEvent.query.filter_by(project_id=project.id).order_by(TimelineEvent.created_at.desc()).all()
    current_stage, latest_rejection = get_project_stage(events)

    return render_template(
        "timeline.html",
        project=project,
        events=events,
        progress_stages=PROGRESS_STAGES,
        current_stage=current_stage,
        latest_rejection=latest_rejection,
        user=user,
        active_project_id=project_id,
    )


@timeline_bp.route("/timeline/add_event", methods=["POST"])
@jwt_required()
def add_timeline_event():
    user = User.query.get(get_jwt_identity())
    if user.role == "Owner":
        return redirect(url_for("owner.owner_home"))
    project_id = request.form.get("project_id", type=int)
    event_type = request.form.get("event_type", "").strip()
    description = request.form.get("description", "").strip()

    if not project_id or not event_type or not description:
        flash("Project, event type, and description are required.", "error")
        return redirect(request.referrer or url_for("document.dashboard"))

    project = Project.query.get_or_404(project_id)

    timeline_event = TimelineEvent(
        project_id=project.id,
        event_type=event_type,
        description=description,
    )
    db.session.add(timeline_event)
    db.session.commit()

    flash("Timeline event added successfully.", "success")
    return redirect(url_for("timeline.timeline", project_id=project.id))


@timeline_bp.route("/timeline/gantt")
@jwt_required()
def gantt():
    user = User.query.get(get_jwt_identity())
    if user.role == "Owner":
        return redirect(url_for("owner.owner_home"))
    projects = Project.query.order_by(Project.name).all()
    return render_template("gantt.html", user=user, projects=projects)


@timeline_bp.route("/public/project/<int:project_id>")
def public_project(project_id):
    project = Project.query.get_or_404(project_id)
    events = TimelineEvent.query.filter_by(project_id=project.id).order_by(TimelineEvent.created_at.desc()).all()
    current_stage, latest_rejection = get_project_stage(events)

    return render_template(
        "public_project.html",
        project=project,
        events=events,
        progress_stages=PROGRESS_STAGES,
        current_stage=current_stage,
        latest_rejection=latest_rejection,
    )
