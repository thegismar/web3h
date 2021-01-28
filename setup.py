import setuptools

setuptools.setup(
    name="w3h",  # Replace with your own username
    version="0.0.5",
    packages=setuptools.find_packages(),
    package_data={'w3h': ['w3h/*.json']},
    include_package_data=True,
    python_requires='>=3.9',
    )
