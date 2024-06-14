class GenericParserException(Exception):
    """Base exception class for PDF parser errors."""

    def __init__(self, message="An error occurred in the PDF parser."):
        super().__init__(message)


class OpenAIKeyError(GenericParserException):
    def __init__(self, message="OpenAI API key is not set."):
        super().__init__(message)


class WrongGPTAnswerError(GenericParserException):
    def __init__(self, message="GPT answered in wrong format."):
        super().__init__(message)
