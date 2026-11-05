"""Handle frozen multiprocessing before importing the native desktop composition."""

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from application import run_application

    run_application()
