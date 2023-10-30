from setuptools import setup, find_packages

setup(
    name='noteri',
    version='0.1.0',
    author='Your Name',
    author_email='ericpar234@gmail.com',
    description='A short description of your project',
    long_description=open('README.md').read(),
    install_requires=[
        'textual>=0.40',
    ],
    python_requires='>=3.7',
    entry_points={
        'console_scripts': [
            'noteri=noteri:main',
        ],
    },
)