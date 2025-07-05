"""Utility functions for URL manipulation."""


def join_urls(*args: str) -> str:
    """
    Join multiple URL components into a single URL.

    :param args: URL components to join.
    :return: Joined URL.
    """
    return "/".join(arg.strip("/") for arg in args if arg.strip("/"))
