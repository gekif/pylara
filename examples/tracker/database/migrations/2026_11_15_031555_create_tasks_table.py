from pylara.database.migration import Migration, Schema


class CreateTasksTable(Migration):

    def up(self):
        return Schema.create("tasks", lambda t: [
            t.id(),
            t.integer("user_id").not_null(),
            t.string("title").not_null(),
            t.boolean("done"),
            t.string("attachment").nullable(),
            t.timestamps(),
            t.foreign("user_id").references("id").on("users"),
        ])

    def down(self):
        return Schema.drop("tasks")
