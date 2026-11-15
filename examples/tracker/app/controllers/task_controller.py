import os

from pylara import Controller, Request
from pylara.http.exceptions import ValidationException

from app.models.task import Task
from app.models.user import User


def current_user(request: Request):
    return User.find(request.session.get("user_id"))


def own_task_or_404(request: Request, id: str) -> Task:
    task = Task.where("id", int(id)).where("user_id", request.session.get("user_id")).first()
    if task is None:
        raise_404()
    return task


def raise_404():
    from pylara.http.response import abort
    abort(404, "Task not found")


class TaskController(Controller):

    def index(self, request: Request):
        user = current_user(request)
        tasks = Task.where("user_id", user.id).order_by("id", "DESC").get()
        return self.view("tasks.index", user=user, tasks=tasks, errors={}, old={})

    def store(self, request: Request):
        user = current_user(request)
        try:
            data = request.validate({"title": "required|min:3|max:100",
                                     "attachment": "file|mimes:png,jpg,pdf|max_kb:100"})
        except ValidationException as exc:
            tasks = Task.where("user_id", user.id).order_by("id", "DESC").get()
            return self.view("tasks.index", user=user, tasks=tasks, errors=exc.errors,
                             old=request.only("title"), status=422)
        stored = None
        if data["attachment"] is not None:
            stored = os.path.basename(data["attachment"].save(os.path.join("storage", "uploads")))
        Task.create(user_id=user.id, title=data["title"], done=0, attachment=stored)
        request.session.flash("status", "Task added.")
        return self.redirect("/tasks")

    def toggle(self, request: Request, id: str):
        task = own_task_or_404(request, id)
        task.done = 0 if task.done else 1
        task.save()
        return self.redirect("/tasks")

    def destroy(self, request: Request, id: str):
        own_task_or_404(request, id).delete()
        request.session.flash("status", "Task deleted.")
        return self.redirect("/tasks")
