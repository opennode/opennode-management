from setuptools import setup, find_packages


setup(
    name = "opennode.oms.test-plugin",
    version = "0.0",
    description = """Test OMS plugin""",
    author = "OpenNode Developers <developers@opennodecloud.com>",
    packages = find_packages(),
    entry_points = {'oms.plugins': ['custom_info_plugin = oms_test_plugin.test:CustomInfoPlugin',
                                    'simple_test_plugin = oms_test_plugin.simple:SimpleTestPlugin',
                                    'callable_plugin = oms_test_plugin.callable:callable_plugin']}
)
