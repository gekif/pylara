from pylara import Model


class User(Model):
    table = "users"
    fillable = ["name", "email", "password"]
    hidden = ["password"]
    timestamps = True

    def posts(self):
        from app.models.post import Post
        return self.has_many(Post)
