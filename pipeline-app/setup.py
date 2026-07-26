from setuptools import find_packages, setup

setup(
    name="pipeline-app",
    version="0.1.0",
    packages=find_packages(include=["pipeline_app", "pipeline_app.*"]),
    package_data={"pipeline_app": ["templates/*.html", "templates/partials/*.html", "static/*.css"]},
)
