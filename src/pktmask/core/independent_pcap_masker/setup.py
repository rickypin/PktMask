#!/usr/bin/env python3
"""
独立PCAP掩码处理器安装配置

本文件定义了独立PCAP掩码处理器模块的安装配置，支持pip安装和发布。
"""

from setuptools import setup, find_packages
import os

# 读取版本信息
def get_version():
    """从__init__.py文件中读取版本信息"""
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, '__init__.py'), 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip('"\'')
    return '1.0.0'

# 读取长描述
def get_long_description():
    """读取README文件作为长描述"""
    here = os.path.abspath(os.path.dirname(__file__))
    readme_path = os.path.join(here, '..', '..', '..', '..', 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "独立的PCAP掩码处理器，基于TCP序列号的精确字节级掩码"

# 读取依赖
def get_requirements():
    """读取依赖包列表"""
    requirements = [
        'scapy>=2.4.0',
        'typing-extensions>=4.0.0;python_version<"3.8"'
    ]
    return requirements

setup(
    name='independent-pcap-masker',
    version=get_version(),
    author='PktMask开发团队',
    author_email='dev@pktmask.org',
    description='独立的PCAP掩码处理器，基于TCP序列号的精确字节级掩码',
    long_description=get_long_description(),
    long_description_content_type='text/markdown',
    url='https://github.com/pktmask/independent-pcap-masker',
    project_urls={
        'Bug Reports': 'https://github.com/pktmask/independent-pcap-masker/issues',
        'Source': 'https://github.com/pktmask/independent-pcap-masker',
        'Documentation': 'https://github.com/pktmask/independent-pcap-masker/docs',
    },
    packages=find_packages(),
    package_dir={'': '.'},
    python_requires='>=3.8',
    install_requires=get_requirements(),
    extras_require={
        'dev': [
            'pytest>=6.0',
            'pytest-cov>=2.0',
            'black>=22.0',
            'flake8>=4.0',
            'mypy>=0.950',
            'isort>=5.0',
        ],
        'test': [
            'pytest>=6.0',
            'pytest-cov>=2.0',
            'pytest-mock>=3.0',
        ],
        'performance': [
            'psutil>=5.0',
            'memory-profiler>=0.60',
        ]
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'Topic :: System :: Networking',
        'Topic :: Security',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Operating System :: OS Independent',
        'Environment :: Console',
    ],
    keywords='pcap masking tcp sequence network security anonymization',
    include_package_data=True,
    package_data={
        'pktmask.core.independent_pcap_masker': [
            'README.md',
            'LICENSE',
            '*.txt'
        ],
    },
    entry_points={
        'console_scripts': [
            'independent-pcap-masker=pktmask.core.independent_pcap_masker.cli:main',
        ],
    },
    zip_safe=False,
    platforms=['any'],
) 