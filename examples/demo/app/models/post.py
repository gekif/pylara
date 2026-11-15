from pylara import Model


class Post(Model):
    table = "posts"
    fillable = ["user_id", "title", "body"]
    timestamps = True

    def author(self):
        from app.models.user import User
        return self.belongs_to(User, foreign_key="user_id")
