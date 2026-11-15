from pylara import Model


class User(Model):
    table = "users"
    fillable = ["name", "email", "password"]
    hidden = ["password"]      # never included in to_dict() / JSON
