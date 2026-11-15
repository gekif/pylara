from pylara import Model


class Task(Model):
    table = "tasks"
    fillable = ["user_id", "title", "done", "attachment"]
    casts = {"done": int}
