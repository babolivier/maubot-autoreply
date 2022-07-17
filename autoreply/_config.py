from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper


class AutoReplyBotConfig(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("message")
        helper.copy("room")
