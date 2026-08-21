def test_backend_import():
    """Verify that backend app can be imported."""
    try:
        import app
    except ImportError as e:
        assert False, f"Failed to import app: {e}"
