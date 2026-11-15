from pylara.database.migration import Migration, Schema


class CreateUsersTable(Migration):

    def up(self):
        return Schema.create("users", lambda t: [
            t.id(),
            t.string("name"),
            t.string("email").unique("email"),
            t.string("password"),
            t.timestamps(),
        ])

    def down(self):
        return Schema.drop("users")
