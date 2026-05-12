from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from app.router import Router
from ui.components.app_sidebar import AppSidebar
from ui.components.app_top_bar import AppTopBar
from ui.pages.editor_page import EditorPage
from ui.pages.export_page import ExportPage
from ui.pages.home_page import HomePage
from ui.pages.import_page import ImportPage
from ui.pages.voices_page import VoicesPage


class EditorLayout(QWidget):
    def __init__(self):
        super().__init__()

        self.router = Router()

        self.sidebar = AppSidebar(on_navigate=self.navigate)
        self.top_bar = AppTopBar()

        self.setup_routes()
        self.setup_layout()

        self.navigate("home")

    def setup_routes(self):
        self.router.add_route("home", HomePage(router=self.router))
        self.router.add_route("import", ImportPage(router=self.router))
        self.router.add_route("editor", EditorPage(router=self.router))
        self.router.add_route("voices", VoicesPage(router=self.router))
        self.router.add_route("export", ExportPage(router=self.router))

    def setup_layout(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        content_container = QWidget()
        content_container.setObjectName("contentContainer")

        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_layout.addWidget(self.top_bar)
        content_layout.addWidget(self.router.stack, 1)

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(content_container, 1)

    def navigate(self, route: str):
        self.router.go_to(route)
        self.sidebar.set_active(route)