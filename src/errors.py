"""カスタムエラークラス。"""


class ContentCreatorError(Exception):
    """基底エラークラス。"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class TemplateNotFoundError(ContentCreatorError):
    """指定タイプのテンプレートが存在しない。"""

    def __init__(self, content_type: str) -> None:
        self.content_type = content_type
        super().__init__(f"テンプレートが見つかりません: {content_type}")


class CollectionError(ContentCreatorError):
    """情報収集エラー。"""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        super().__init__(f"[{source}] {message}")


class WordPressPublishError(ContentCreatorError):
    """WordPress投稿エラー。"""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        if status_code:
            super().__init__(f"{message} (HTTP {status_code})")
        else:
            super().__init__(message)


class XPublishError(ContentCreatorError):
    """X投稿エラー。"""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        if status_code:
            super().__init__(f"{message} (HTTP {status_code})")
        else:
            super().__init__(message)


class DraftSaveError(ContentCreatorError):
    """ドラフト保存エラー。"""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        super().__init__(f"ドラフト保存エラー [{path}]: {message}")
