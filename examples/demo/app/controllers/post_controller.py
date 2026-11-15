from pylara import Controller, Request
from app.models.post import Post


class PostController(Controller):

    def index(self, request: Request):
        page = int(request.query("page", 1))
        result = Post.query().order_by("created_at", "DESC").paginate(per_page=10, page=page)
        result["data"] = [p.to_dict() for p in result["data"]]
        return self.json(result)

    def show(self, request: Request, id: str):
        post = Post.find_or_fail(int(id))
        data = post.to_dict()
        author = post.author()
        data["author"] = author.to_dict() if author else None
        return self.json(data)

    def store(self, request: Request):
        data = request.validate({
            "user_id": "required|integer",
            "title": "required|string|max:255",
            "body": "required|string",
        })
        post = Post.create(**data)
        return self.json(post.to_dict(), 201)

    def update(self, request: Request, id: str):
        post = Post.find_or_fail(int(id))
        data = request.only("title", "body")
        for k, v in data.items():
            setattr(post, k, v)
        post.save()
        return self.json(post.to_dict())

    def destroy(self, request: Request, id: str):
        post = Post.find_or_fail(int(id))
        post.delete()
        return self.json({"message": f"Post {id} deleted."})
