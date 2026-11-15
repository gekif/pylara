from pylara.database.migration import Migration, Schema


class CreatePostsTable(Migration):

    def up(self):
        return Schema.create("posts", lambda t: [
            t.id(),
            t.integer("user_id"),
            t.string("title"),
            t.text("body"),
            t.timestamps(),
            t.foreign("user_id").references("id").on("users"),
        ])

    def down(self):
        return Schema.drop("posts")
