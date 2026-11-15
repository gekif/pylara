from pylara.support.service_provider import ServiceProvider


class AppServiceProvider(ServiceProvider):

    def register(self):
        """Bind things into the container. Runs before boot()."""
        # self.app.singleton("mailer", lambda app: Mailer(app.env("MAIL_HOST")))

    def boot(self):
        """Runs once every provider has been registered."""
