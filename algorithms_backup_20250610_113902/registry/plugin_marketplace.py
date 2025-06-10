#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
插件市场和API标准 - Phase 6.4
支持第三方插件集成和标准化开发接口
"""

import json
import hashlib
import zipfile
import tempfile
import shutil
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Type
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from urllib.parse import urlparse
import semantic_version

from ..interfaces.algorithm_interface import (
    AlgorithmInterface, AlgorithmInfo, AlgorithmType, AlgorithmDependency
)
from .plugin_discovery import PluginCandidate, PluginSource
from .dependency_resolver import get_dependency_resolver
from ...infrastructure.logging import get_logger
from ...common.exceptions import PluginError, ValidationError


class PluginLicense(Enum):
    """插件许可证类型"""
    MIT = "MIT"
    BSD = "BSD"
    GPL_V3 = "GPL-3.0"
    APACHE_2 = "Apache-2.0"
    LGPL = "LGPL"
    PROPRIETARY = "Proprietary"
    CUSTOM = "Custom"


class PluginCategory(Enum):
    """插件分类"""
    IP_ANONYMIZATION = "ip_anonymization"
    PACKET_PROCESSING = "packet_processing"
    DEDUPLICATION = "deduplication"
    FILTERING = "filtering"
    ANALYSIS = "analysis"
    VISUALIZATION = "visualization"
    EXPORT = "export"
    UTILITY = "utility"
    CUSTOM = "custom"


class PluginQuality(Enum):
    """插件质量级别"""
    EXPERIMENTAL = "experimental"  # 实验性
    BETA = "beta"                 # 测试版
    STABLE = "stable"             # 稳定版
    PRODUCTION = "production"     # 生产级
    DEPRECATED = "deprecated"     # 已弃用


@dataclass
class PluginManifest:
    """插件清单"""
    # 基本信息
    name: str
    version: str
    description: str
    author: str
    author_email: str
    homepage: str = ""
    repository: str = ""
    
    # 分类和标签
    category: PluginCategory = PluginCategory.CUSTOM
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    # 许可证
    license: PluginLicense = PluginLicense.MIT
    license_text: str = ""
    
    # 技术信息
    algorithm_type: AlgorithmType = AlgorithmType.CUSTOM
    min_python_version: str = "3.8.0"
    max_python_version: str = ""
    supported_platforms: List[str] = field(default_factory=lambda: ["any"])
    
    # 依赖
    dependencies: List[AlgorithmDependency] = field(default_factory=list)
    
    # 质量和兼容性
    quality: PluginQuality = PluginQuality.EXPERIMENTAL
    api_version: str = "1.0"
    pktmask_min_version: str = "1.0.0"
    pktmask_max_version: str = ""
    
    # 文件信息
    main_module: str = "plugin.py"
    test_module: str = ""
    documentation: str = ""
    changelog: str = ""
    
    # 元数据
    created_at: str = ""
    updated_at: str = ""
    download_count: int = 0
    rating: float = 0.0
    rating_count: int = 0
    
    # 验证
    signature: str = ""
    checksum: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 处理枚举类型
        data['category'] = self.category.value
        data['license'] = self.license.value
        data['algorithm_type'] = self.algorithm_type.value
        data['quality'] = self.quality.value
        data['dependencies'] = [asdict(dep) for dep in self.dependencies]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginManifest':
        """从字典创建"""
        # 处理枚举类型
        if 'category' in data:
            data['category'] = PluginCategory(data['category'])
        if 'license' in data:
            data['license'] = PluginLicense(data['license'])
        if 'algorithm_type' in data:
            data['algorithm_type'] = AlgorithmType(data['algorithm_type'])
        if 'quality' in data:
            data['quality'] = PluginQuality(data['quality'])
        if 'dependencies' in data:
            data['dependencies'] = [AlgorithmDependency(**dep) for dep in data['dependencies']]
        
        return cls(**data)
    
    def validate(self) -> List[str]:
        """验证清单"""
        errors = []
        
        # 基本验证
        if not self.name:
            errors.append("插件名称不能为空")
        if not self.version:
            errors.append("插件版本不能为空")
        if not self.description:
            errors.append("插件描述不能为空")
        if not self.author:
            errors.append("插件作者不能为空")
        
        # 版本验证
        try:
            semantic_version.Version(self.version)
        except ValueError:
            errors.append("插件版本格式无效")
        
        # Python版本验证
        try:
            semantic_version.Version(self.min_python_version)
        except ValueError:
            errors.append("最小Python版本格式无效")
        
        if self.max_python_version:
            try:
                semantic_version.Version(self.max_python_version)
            except ValueError:
                errors.append("最大Python版本格式无效")
        
        # 文件验证
        if not self.main_module:
            errors.append("主模块不能为空")
        
        return errors


@dataclass
class PluginPackage:
    """插件包"""
    manifest: PluginManifest
    file_path: Optional[Path] = None
    content: Optional[bytes] = None
    source_url: Optional[str] = None
    local_path: Optional[Path] = None
    installed: bool = False
    installed_at: Optional[datetime] = None


class PluginValidator:
    """插件验证器"""
    
    def __init__(self):
        self._logger = get_logger('plugin.validator')
        self._dependency_resolver = get_dependency_resolver()
    
    def validate_manifest(self, manifest: PluginManifest) -> List[str]:
        """验证插件清单"""
        return manifest.validate()
    
    def validate_package(self, package: PluginPackage) -> List[str]:
        """验证插件包"""
        errors = []
        
        # 验证清单
        manifest_errors = self.validate_manifest(package.manifest)
        errors.extend(manifest_errors)
        
        # 验证文件结构
        if package.file_path and package.file_path.exists():
            structure_errors = self._validate_package_structure(package)
            errors.extend(structure_errors)
        
        # 验证代码
        if package.local_path and package.local_path.exists():
            code_errors = self._validate_code(package)
            errors.extend(code_errors)
        
        return errors
    
    def _validate_package_structure(self, package: PluginPackage) -> List[str]:
        """验证包结构"""
        errors = []
        
        try:
            if package.file_path.suffix.lower() == '.zip':
                with zipfile.ZipFile(package.file_path, 'r') as zip_file:
                    files = zip_file.namelist()
                    
                    # 检查清单文件
                    if 'manifest.json' not in files:
                        errors.append("缺少 manifest.json 文件")
                    
                    # 检查主模块
                    if package.manifest.main_module not in files:
                        errors.append(f"缺少主模块文件: {package.manifest.main_module}")
                    
                    # 检查Python文件
                    python_files = [f for f in files if f.endswith('.py')]
                    if not python_files:
                        errors.append("包中没有Python文件")
        
        except Exception as e:
            errors.append(f"验证包结构失败: {e}")
        
        return errors
    
    def _validate_code(self, package: PluginPackage) -> List[str]:
        """验证代码"""
        errors = []
        
        try:
            main_module_path = package.local_path / package.manifest.main_module
            if not main_module_path.exists():
                errors.append(f"主模块文件不存在: {package.manifest.main_module}")
                return errors
            
            # 基本语法检查
            with open(main_module_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            try:
                compile(code, str(main_module_path), 'exec')
            except SyntaxError as e:
                errors.append(f"语法错误: {e}")
            
            # 检查是否包含AlgorithmInterface实现
            if 'class' not in code or 'AlgorithmInterface' not in code:
                errors.append("未找到AlgorithmInterface实现类")
        
        except Exception as e:
            errors.append(f"验证代码失败: {e}")
        
        return errors
    
    def calculate_checksum(self, file_path: Path) -> str:
        """计算文件校验和"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            self._logger.error(f"计算校验和失败: {e}")
            return ""


class PluginRepository:
    """插件仓库"""
    
    def __init__(self, base_url: str, cache_dir: Optional[Path] = None):
        self._base_url = base_url.rstrip('/')
        self._cache_dir = cache_dir or Path.home() / ".pktmask" / "plugin_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._logger = get_logger('plugin.repository')
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'PktMask-PluginManager/1.0'
        })
    
    def search_plugins(
        self,
        query: str = "",
        category: Optional[PluginCategory] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[PluginManifest]:
        """搜索插件"""
        try:
            params = {
                'q': query,
                'limit': limit
            }
            
            if category:
                params['category'] = category.value
            
            if tags:
                params['tags'] = ','.join(tags)
            
            response = self._session.get(
                f"{self._base_url}/api/plugins/search",
                params=params
            )
            response.raise_for_status()
            
            plugins_data = response.json()
            plugins = []
            
            for plugin_data in plugins_data.get('plugins', []):
                try:
                    manifest = PluginManifest.from_dict(plugin_data)
                    plugins.append(manifest)
                except Exception as e:
                    self._logger.warning(f"解析插件清单失败: {e}")
            
            self._logger.info(f"搜索到 {len(plugins)} 个插件")
            return plugins
        
        except Exception as e:
            self._logger.error(f"搜索插件失败: {e}")
            return []
    
    def get_plugin_details(self, plugin_name: str, version: str = "latest") -> Optional[PluginManifest]:
        """获取插件详情"""
        try:
            response = self._session.get(
                f"{self._base_url}/api/plugins/{plugin_name}/{version}"
            )
            response.raise_for_status()
            
            plugin_data = response.json()
            return PluginManifest.from_dict(plugin_data)
        
        except Exception as e:
            self._logger.error(f"获取插件详情失败 {plugin_name}: {e}")
            return None
    
    def download_plugin(self, plugin_name: str, version: str = "latest") -> Optional[PluginPackage]:
        """下载插件"""
        try:
            # 获取下载URL
            response = self._session.get(
                f"{self._base_url}/api/plugins/{plugin_name}/{version}/download"
            )
            response.raise_for_status()
            
            download_info = response.json()
            download_url = download_info['download_url']
            manifest_data = download_info['manifest']
            
            # 创建清单
            manifest = PluginManifest.from_dict(manifest_data)
            
            # 下载文件
            cache_file = self._cache_dir / f"{plugin_name}-{version}.zip"
            
            with self._session.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(cache_file, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
            
            package = PluginPackage(
                manifest=manifest,
                file_path=cache_file,
                source_url=download_url
            )
            
            self._logger.info(f"成功下载插件: {plugin_name} v{version}")
            return package
        
        except Exception as e:
            self._logger.error(f"下载插件失败 {plugin_name}: {e}")
            return None
    
    def upload_plugin(self, package_path: Path, api_key: str) -> bool:
        """上传插件"""
        try:
            # 读取清单
            with zipfile.ZipFile(package_path, 'r') as zip_file:
                manifest_data = json.loads(zip_file.read('manifest.json'))
                manifest = PluginManifest.from_dict(manifest_data)
            
            # 上传文件
            with open(package_path, 'rb') as f:
                files = {'file': f}
                headers = {'Authorization': f'Bearer {api_key}'}
                
                response = self._session.post(
                    f"{self._base_url}/api/plugins/upload",
                    files=files,
                    headers=headers
                )
                response.raise_for_status()
            
            self._logger.info(f"成功上传插件: {manifest.name} v{manifest.version}")
            return True
        
        except Exception as e:
            self._logger.error(f"上传插件失败: {e}")
            return False


class PluginMarketplace:
    """插件市场"""
    
    def __init__(self):
        self._logger = get_logger('plugin.marketplace')
        self._validator = PluginValidator()
        self._repositories: Dict[str, PluginRepository] = {}
        self._installed_plugins: Dict[str, PluginPackage] = {}
        self._install_dir = Path.home() / ".pktmask" / "plugins"
        self._install_dir.mkdir(parents=True, exist_ok=True)
        
        # 添加默认仓库
        self.add_repository(
            "official",
            "https://plugins.pktmask.org"  # 假设的官方仓库
        )
    
    def add_repository(self, name: str, url: str) -> bool:
        """添加插件仓库"""
        try:
            repository = PluginRepository(url)
            self._repositories[name] = repository
            self._logger.info(f"添加插件仓库: {name} ({url})")
            return True
        except Exception as e:
            self._logger.error(f"添加插件仓库失败 {name}: {e}")
            return False
    
    def remove_repository(self, name: str) -> bool:
        """移除插件仓库"""
        if name in self._repositories:
            del self._repositories[name]
            self._logger.info(f"移除插件仓库: {name}")
            return True
        return False
    
    def search_plugins(
        self,
        query: str = "",
        category: Optional[PluginCategory] = None,
        repository: Optional[str] = None
    ) -> List[PluginManifest]:
        """搜索插件"""
        all_plugins = []
        
        repositories = [self._repositories[repository]] if repository else self._repositories.values()
        
        for repo in repositories:
            try:
                plugins = repo.search_plugins(query, category)
                all_plugins.extend(plugins)
            except Exception as e:
                self._logger.error(f"搜索仓库失败: {e}")
        
        # 去重（按名称和版本）
        unique_plugins = {}
        for plugin in all_plugins:
            key = f"{plugin.name}:{plugin.version}"
            if key not in unique_plugins:
                unique_plugins[key] = plugin
        
        return list(unique_plugins.values())
    
    def install_plugin(
        self,
        plugin_name: str,
        version: str = "latest",
        repository: Optional[str] = None,
        force: bool = False
    ) -> bool:
        """安装插件"""
        try:
            # 检查是否已安装
            if plugin_name in self._installed_plugins and not force:
                self._logger.info(f"插件已安装: {plugin_name}")
                return True
            
            # 下载插件
            package = None
            repositories = [self._repositories[repository]] if repository else self._repositories.values()
            
            for repo in repositories:
                try:
                    package = repo.download_plugin(plugin_name, version)
                    if package:
                        break
                except Exception as e:
                    self._logger.warning(f"从仓库下载失败: {e}")
            
            if not package:
                self._logger.error(f"无法下载插件: {plugin_name}")
                return False
            
            # 验证插件
            validation_errors = self._validator.validate_package(package)
            if validation_errors:
                self._logger.error(f"插件验证失败: {', '.join(validation_errors)}")
                return False
            
            # 安装插件
            install_path = self._install_dir / plugin_name
            install_path.mkdir(exist_ok=True)
            
            # 解压文件
            with zipfile.ZipFile(package.file_path, 'r') as zip_file:
                zip_file.extractall(install_path)
            
            # 更新包信息
            package.local_path = install_path
            package.installed = True
            package.installed_at = datetime.now()
            
            self._installed_plugins[plugin_name] = package
            
            self._logger.info(f"成功安装插件: {plugin_name} v{package.manifest.version}")
            return True
        
        except Exception as e:
            self._logger.error(f"安装插件失败 {plugin_name}: {e}")
            return False
    
    def uninstall_plugin(self, plugin_name: str) -> bool:
        """卸载插件"""
        try:
            if plugin_name not in self._installed_plugins:
                self._logger.warning(f"插件未安装: {plugin_name}")
                return False
            
            package = self._installed_plugins[plugin_name]
            
            # 删除文件
            if package.local_path and package.local_path.exists():
                shutil.rmtree(package.local_path)
            
            # 移除记录
            del self._installed_plugins[plugin_name]
            
            self._logger.info(f"成功卸载插件: {plugin_name}")
            return True
        
        except Exception as e:
            self._logger.error(f"卸载插件失败 {plugin_name}: {e}")
            return False
    
    def list_installed_plugins(self) -> List[PluginPackage]:
        """列出已安装的插件"""
        return list(self._installed_plugins.values())
    
    def update_plugin(self, plugin_name: str) -> bool:
        """更新插件"""
        if plugin_name not in self._installed_plugins:
            self._logger.error(f"插件未安装: {plugin_name}")
            return False
        
        current_package = self._installed_plugins[plugin_name]
        current_version = current_package.manifest.version
        
        # 检查最新版本
        latest_manifest = None
        for repo in self._repositories.values():
            try:
                latest_manifest = repo.get_plugin_details(plugin_name, "latest")
                if latest_manifest:
                    break
            except Exception:
                continue
        
        if not latest_manifest:
            self._logger.error(f"无法获取插件最新版本: {plugin_name}")
            return False
        
        # 比较版本
        try:
            current_ver = semantic_version.Version(current_version)
            latest_ver = semantic_version.Version(latest_manifest.version)
            
            if latest_ver <= current_ver:
                self._logger.info(f"插件已是最新版本: {plugin_name}")
                return True
        except ValueError:
            self._logger.warning("版本比较失败，强制更新")
        
        # 执行更新
        return self.install_plugin(plugin_name, latest_manifest.version, force=True)
    
    def create_plugin_template(self, plugin_name: str, output_dir: Path) -> bool:
        """创建插件模板"""
        try:
            template_dir = output_dir / plugin_name
            template_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建清单文件
            manifest = PluginManifest(
                name=plugin_name,
                version="0.1.0",
                description=f"A custom plugin: {plugin_name}",
                author="Your Name",
                author_email="your.email@example.com",
                main_module="plugin.py"
            )
            
            manifest_path = template_dir / "manifest.json"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
            
            # 创建主模块文件
            plugin_code = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
{plugin_name} - 自定义插件
"""

from typing import Dict, Any, List
from pktmask.algorithms.interfaces.algorithm_interface import (
    AlgorithmInterface, AlgorithmInfo, AlgorithmType, AlgorithmDependency
)


class {plugin_name.replace('_', '').title()}Plugin(AlgorithmInterface):
    """
    {plugin_name} 插件实现
    """
    
    def __init__(self):
        super().__init__()
        self._logger = self._get_logger()
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        """获取算法信息"""
        return AlgorithmInfo(
            name="{plugin_name}",
            version="0.1.0",
            description="A custom plugin: {plugin_name}",
            algorithm_type=AlgorithmType.CUSTOM,
            author="Your Name",
            dependencies=[
                # 添加依赖项，例如：
                # AlgorithmDependency(
                #     name="numpy",
                #     version_spec=">=1.20.0",
                #     dependency_type=DependencyType.REQUIRED
                # )
            ]
        )
    
    def process(self, data: Any, **kwargs) -> Any:
        """
        处理数据
        
        Args:
            data: 输入数据
            **kwargs: 其他参数
            
        Returns:
            Any: 处理后的数据
        """
        # 在这里实现您的算法逻辑
        self._logger.info(f"处理数据: {{type(data)}}")
        
        # 示例：直接返回输入数据
        return data
    
    def cleanup(self):
        """清理资源"""
        self._logger.info("清理资源")
        super().cleanup()
'''
            
            plugin_path = template_dir / "plugin.py"
            with open(plugin_path, 'w', encoding='utf-8') as f:
                f.write(plugin_code)
            
            # 创建README文件
            readme_content = f'''# {plugin_name}

## 描述
{plugin_name} 是一个自定义PktMask插件。

## 安装
将此目录复制到PktMask插件目录中。

## 使用
插件会自动被PktMask发现和加载。

## 开发
修改 `plugin.py` 文件以实现您的算法逻辑。
'''
            
            readme_path = template_dir / "README.md"
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            
            self._logger.info(f"成功创建插件模板: {template_dir}")
            return True
        
        except Exception as e:
            self._logger.error(f"创建插件模板失败: {e}")
            return False
    
    def package_plugin(self, plugin_dir: Path, output_path: Optional[Path] = None) -> Optional[Path]:
        """打包插件"""
        try:
            manifest_path = plugin_dir / "manifest.json"
            if not manifest_path.exists():
                self._logger.error("缺少manifest.json文件")
                return None
            
            # 读取清单
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
                manifest = PluginManifest.from_dict(manifest_data)
            
            # 确定输出路径
            if output_path is None:
                output_path = plugin_dir.parent / f"{manifest.name}-{manifest.version}.zip"
            
            # 创建ZIP包
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in plugin_dir.rglob('*'):
                    if file_path.is_file():
                        arc_name = file_path.relative_to(plugin_dir)
                        zip_file.write(file_path, arc_name)
            
            # 计算校验和
            checksum = self._validator.calculate_checksum(output_path)
            manifest.checksum = checksum
            
            # 更新清单中的校验和
            with zipfile.ZipFile(output_path, 'a') as zip_file:
                zip_file.writestr('manifest.json', json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False))
            
            self._logger.info(f"成功打包插件: {output_path}")
            return output_path
        
        except Exception as e:
            self._logger.error(f"打包插件失败: {e}")
            return None
    
    def get_marketplace_stats(self) -> Dict[str, Any]:
        """获取市场统计信息"""
        return {
            "repositories": len(self._repositories),
            "installed_plugins": len(self._installed_plugins),
            "repository_list": list(self._repositories.keys()),
            "installed_list": [p.manifest.name for p in self._installed_plugins.values()]
        }


# 全局插件市场实例
_plugin_marketplace: Optional[PluginMarketplace] = None


def get_plugin_marketplace() -> PluginMarketplace:
    """获取全局插件市场实例"""
    global _plugin_marketplace
    if _plugin_marketplace is None:
        _plugin_marketplace = PluginMarketplace()
    return _plugin_marketplace 