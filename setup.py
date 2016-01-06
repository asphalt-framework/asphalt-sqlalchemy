import os.path

from setuptools import setup

here = os.path.dirname(__file__)
readme_path = os.path.join(here, 'README.rst')
readme = open(readme_path).read()

setup(
    name='asphalt-sqlalchemy',
    use_scm_version={
        'local_scheme': 'dirty-tag'
    },
    description='SQLAlchemy integration component for the Asphalt framework',
    long_description=readme,
    author='Alex Grönholm',
    author_email='alex.gronholm@nextday.fi',
    url='https://github.com/asphalt-framework/asphalt-sqlalchemy',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Topic :: Database',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5'
    ],
    license='Apache License 2.0',
    zip_safe=False,
    packages=[
        'asphalt.sqlalchemy'
    ],
    setup_requires=[
        'setuptools_scm >= 1.7.0'
    ],
    install_requires=[
        'asphalt >= 1.2, < 2.0',
        'SQLAlchemy >= 1.0.10'
    ],
    entry_points={
        'asphalt.components': [
            'sqlalchemy = asphalt.sqlalchemy.component:SQLAlchemyComponent'
        ]
    }
)
