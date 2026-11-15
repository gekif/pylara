from pylara import Controller, Request, JsonResponse
from pylara.support.hashing import Hash
from app.models.user import User


class UserController(Controller):

    def index(self, request: Request):
        users = User.all()
        return self.json([u.to_dict() for u in users])

    def show(self, request: Request, id: str):
        user = User.find_or_fail(int(id))
        data = user.to_dict()
        data["posts"] = [p.to_dict() for p in user.posts()]
        return self.json(data)

    def store(self, request: Request):
        data = request.validate({
            "name": "required|string|max:255",
            "email": "required|email",
            "password": "required|min:6",
        })
        data["password"] = Hash.make(data["password"])
        user = User.create(**data)
        return self.json(user.to_dict(), 201)

    def update(self, request: Request, id: str):
        user = User.find_or_fail(int(id))
        data = request.only("name", "email")
        for k, v in data.items():
            setattr(user, k, v)
        user.save()
        return self.json(user.to_dict())

    def destroy(self, request: Request, id: str):
        user = User.find_or_fail(int(id))
        user.delete()
        return self.json({"message": f"User {id} deleted."})
