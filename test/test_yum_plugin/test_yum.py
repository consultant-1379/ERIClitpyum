##############################################################################
# COPYRIGHT Ericsson AB 2013
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

from yum_plugin.yum_plugin import YumPlugin
from yum_extension.yum_extension import YumExtension
from litp.extensions.core_extension import CoreExtension
from litp.core.model_manager import ModelManager
from litp.core.plugin_manager import PluginManager
from litp.core.plugin_context_api import PluginApiContext
from litp.core.model_type import ItemType, Child, Collection
import socket
import hashlib
import unittest
import os
import sys
from mock import MagicMock, patch, Mock, mock_open
from litp.core.translator import Translator
from litp.core.validators import ValidationError
from litp.core import constants

t = Translator('ERIClitpyum_CXP9030585')
_ = t._


class TestYumPlugin(unittest.TestCase):

    def setUp(self):
        """
        Construct a model, sufficient for test cases
        that you wish to implement in this suite.
        """
        self.model = ModelManager()
        self.plugin_manager = PluginManager(self.model)
        self.context = PluginApiContext(self.model)
        self.plugin_manager.add_property_types(
            CoreExtension().define_property_types())
        self.plugin_manager.add_item_types(
            CoreExtension().define_item_types())

        self.plugin_manager.add_property_types(
            YumExtension().define_property_types())
        self.plugin_manager.add_item_types(
            YumExtension().define_item_types())

        self.plugin = YumPlugin()
        self.plugin_manager.add_plugin('TestPlugin', 'some.test.plugin',
                                       '1.0.0', self.plugin)

        self.model.register_item_type(
            ItemType(
                "another-node",
                extend_item="node"))

        self.model.register_item_type(
            ItemType(
                "root1",
                node1=Child("node"),
                ms=Child("ms"),
                items=Collection("software-item")
            )
        )
        self.setup_model()

    def setup_model(self):
        self.root = self.model.create_root_item("root1", "/")
        self.node1 = self.model.create_item(
            "node", "/node1", hostname="node1")
        self.swp = socket.gethostname
        socket.gethostname = lambda: "mshost"
        self.model.create_item(
            "ms", "/ms", hostname="mshost")
        self.yum1 = self.model.create_item(
            "yum-repository",
            "/items/yum1",
            base_url="file:///tmp/repo",
            name="yum_repo1",
        )
        self.yum2 = self.model.create_item(
            "yum-repository",
            "/items/yum2",
            ms_url_path="/tmp/repo",
            name="yum_repo2",
            cache_metadata="true",
        )
        self.yum3 = self.model.create_item(
            "yum-repository",
            "/items/yum3",
            ms_url_path="/yum3",
            name="yum3",
            cache_metadata="true",
            checksum='7bc3a60fbf38e98f6fef654afa26d270'
        )

    def tearDown(self):
        self.model.remove_item("/node1/items/yum1")
        self.model.remove_item("/items/yum1")
        socket.gethostname = self.swp

    def query(self, item_type=None, **kwargs):
        return self.context.query(item_type, **kwargs)

    def test_item_prop_updated_except(self):
        e1 = MagicMock()
        e1.applied_properties = {'p1': 1, 'p2': 10, 'p3': 5}
        e1.properties = {'p1': 5, 'p2': 20, 'p3': 5}
        e1.__dict__.update(e1.properties)
        plugin = YumPlugin()
        self.assertFalse(plugin._item_updated_except(e1, ['p1', 'p2']))
        self.assertTrue(plugin._item_updated_except(e1, ['p3']))
        self.assertTrue(plugin._item_updated_except(e1, ['p2']))
        self.assertTrue(plugin._item_updated_except(e1, ['p1']))

    def test_item_prop_updated_only(self):
        e1 = MagicMock()
        e1.applied_properties = {'p1': 1, 'p2': 10, 'p3': 5}
        e1.properties = {'p1': 5, 'p2': 20, 'p3': 5}
        e1.__dict__.update(e1.properties)
        plugin = YumPlugin()
        self.assertFalse(plugin._item_updated_only(e1, ['p3']))
        self.assertTrue(plugin._item_updated_only(e1, ['p2']))
        self.assertTrue(plugin._item_updated_only(e1, ['p1']))
        self.assertTrue(plugin._item_updated_only(e1, ['p1', 'p2']))


    def test_add_new_repo_tasks(self):
        yum_link = self.model.create_inherited('/items/yum1',
                                               '/node1/items/yum1')
        tasks = self.plugin.create_configuration(self)
        task = tasks[0]
        yumrep = self.context.query('yum-repository')[0]
        self.assertEqual(1, len(tasks))
        self.assertEqual(self.node1.get_vpath(), task.node.get_vpath())
        self.assertEqual('yumrepo', task.call_type)
        self.assertEqual('yum_repo1', task.call_id)
        self.assertEqual(
            {'gpgcheck': '0', 'enabled': '1',
             'metadata_expire': '0',
             'baseurl': 'file:///tmp/repo',
             'name': 'yum_repo1', 'skip_if_unavailable': '1', 'descr': 'yum_repo1'},
            task.kwargs)
        self.assertEqual(yum_link.get_vpath(), task.model_item.get_vpath())

    def test_add_new_repo_with_name(self):
        yum_link = self.model.create_inherited('/items/yum2',
                                               '/node1/items/yum2')
        tasks = self.plugin.create_configuration(self)
        task = tasks[0]
        expected = set(['/items/yum2',
                        '/node1/items/yum2'])
        actual = set(x.vpath for x in task.all_model_items)
        self.assertEqual(expected, actual)
        yumrep = self.context.query('yum-repository')[0]
        self.assertEqual(1, len(tasks))
        self.assertEqual(self.node1.get_vpath(), task.node.get_vpath())
        self.assertEqual('yumrepo', task.call_type)
        self.assertEqual('yum_repo2', task.call_id)
        self.assertEqual(
            {'gpgcheck': '0', 'enabled': '1',
             'metadata_expire': 'absent',
             'baseurl': 'http://mshost/tmp/repo',
             'name': 'yum_repo2', 'skip_if_unavailable': '1',
             'descr': 'yum_repo2'},
            task.kwargs)
        self.assertEqual(yum_link.get_vpath(), task.model_item.get_vpath())

    def test_add_updated_repo_tasks(self):
        yum_link = self.model.create_inherited('/items/yum1',
                                               '/node1/items/yum1')
        yum_link.set_applied()
        self.model.update_item(
            "/items/yum1", base_url="file:///tmp/repo_updated"
        )

        tasks = self.plugin.create_configuration(self)
        self.assertEqual(2, len(tasks))
        task = tasks[0]
        expected = set(['/items/yum1',
                        '/node1/items/yum1'])
        actual = set(x.vpath for x in task.all_model_items)
        self.assertEqual(expected, actual)
        self.assertEqual(self.node1.get_vpath(), task.node.get_vpath())
        self.assertEqual('yumrepo', task.call_type)
        self.assertEqual('yum_repo1', task.call_id)
        self.assertEqual(
            {'gpgcheck': '0', 'enabled': '1',
             'metadata_expire': '0',
             'baseurl': 'file:///tmp/repo_updated',
             'name': 'yum_repo1',
             'skip_if_unavailable': '1', 'descr': 'yum_repo1'
             }, task.kwargs)
        self.assertEqual(yum_link.get_vpath(),
                         task.model_item.get_vpath())

        task = tasks[1]
        self.assertEqual('_clean_metadata_callback', task.call_type)

    @patch.object(YumPlugin, '_is_upgrade_flag_set', Mock(return_value=True))
    def test_add_updated_repo_tasks_lms_redeploy(self):
        yum_link = self.model.create_inherited('/items/yum1',
                                               '/node1/items/yum1')
        yum_link_ms_1 = self.model.create_inherited('/items/yum1',
                                               '/ms/items/yum1')
        yum_link_ms_2 = self.model.create_inherited('/items/yum2',
                                               '/ms/items/yum2')
        yum_link.set_applied()
        yum_link_ms_1.set_applied()

        self.model.update_item(
            "/items/yum1", base_url="file:///tmp/repo_updated"
        )
        tasks = self.plugin.create_configuration(self)
        self.assertEqual(3, len(tasks))
        task = tasks[0]
        expected = set(['/items/yum2',
                        '/ms/items/yum2'])
        self.assertEqual(yum_link_ms_2.get_vpath(),
                         task.model_item.get_vpath())
        actual = set(x.vpath for x in task.all_model_items)
        self.assertEqual(expected, actual)
        self.assertEqual('/ms', task.node.get_vpath())
        self.assertEqual('yumrepo', task.call_type)
        self.assertEqual('yum_repo2', task.call_id)
        self.assertEqual(
            {'gpgcheck': '0', 'enabled': '1',
             'metadata_expire': 'absent',
             'baseurl': 'http://mshost/tmp/repo',
             'name': 'yum_repo2', 'skip_if_unavailable': '1',
             'descr': 'yum_repo2'},
            task.kwargs)

        expected = set(['/items/yum1',
                        '/ms/items/yum1'])
        task = tasks[1]
        self.assertEqual(yum_link_ms_1.get_vpath(),
                         task.model_item.get_vpath())
        actual = set(x.vpath for x in task.all_model_items)
        self.assertEqual(expected, actual)
        self.assertEqual('/ms', task.node.get_vpath())
        self.assertEqual('yumrepo', task.call_type)
        self.assertEqual('yum_repo1', task.call_id)
        self.assertEqual(
            {'gpgcheck': '0', 'enabled': '1',
             'metadata_expire': '0',
             'baseurl': 'file:///tmp/repo_updated',
             'name': 'yum_repo1',
             'skip_if_unavailable': '1', 'descr': 'yum_repo1'
             }, task.kwargs)

        task = tasks[2]
        self.assertEqual('_clean_metadata_callback', task.call_type)

    def test_add_removal_repo_tasks(self):
        yum_link = self.model.create_inherited('/items/yum1',
                                               '/node1/items/yum1')
        self.model.remove_item("/node1/items/yum1")

        tasks = self.plugin.create_configuration(self)
        self.assertEqual(0, len(tasks))

    def test_validate_model(self):
        errors = self.plugin.validate_model(self)
        self.assertEqual(0, len(errors))

    def test_validate_model_negative(self):
        self.model.create_inherited('/items/yum1', '/node1/items/yum1')
        self.model.create_inherited('/items/yum1', '/node1/items/yum2')
        self.model.create_inherited('/items/yum1', '/node1/items/yum3')
        self.model.create_inherited('/items/yum3', '/node1/items/yum4')
        self.model.create_inherited('/items/yum3', '/node1/items/yum5')
        errors = self.plugin.validate_model(self)
        ref_errors = [ValidationError(item_path = ("/node1/items/yum1"),
                                      error_message = (_('NON_UNIQUE_FIELD_NAME') % ('name', 'yum_repo1')),
                                      error_type=constants.VALIDATION_ERROR),
                      ValidationError(item_path = ("/node1/items/yum2"),
                                      error_message = (_('NON_UNIQUE_FIELD_NAME') % ('name', 'yum_repo1')),
                                      error_type=constants.VALIDATION_ERROR),
                      ValidationError(item_path = ("/node1/items/yum3"),
                                      error_message = (_('NON_UNIQUE_FIELD_NAME') % ('name', 'yum_repo1')),
                                      error_type=constants.VALIDATION_ERROR),
                      ValidationError(item_path = ("/node1/items/yum1"),
                                      error_message = (_('NON_UNIQUE_FIELD_NAME') % ('base_url', 'file:///tmp/repo')),
                                      error_type=constants.VALIDATION_ERROR),
                      ValidationError(item_path = ("/node1/items/yum2"),
                                      error_message = (_('NON_UNIQUE_FIELD_NAME') % ('base_url', 'file:///tmp/repo')),
                                      error_type=constants.VALIDATION_ERROR),
                      ValidationError(item_path = ("/node1/items/yum3"),
                                      error_message = (_('NON_UNIQUE_FIELD_NAME') % ('base_url', 'file:///tmp/repo')),
                                      error_type=constants.VALIDATION_ERROR),
                      ValidationError(item_path = ("/node1/items/yum4"),
                                      error_message = (_('NON_UNIQUE_FIELD_NAME') % ('name', 'yum3')),
                                      error_type=constants.VALIDATION_ERROR),
                      ValidationError(item_path = ("/node1/items/yum5"),
                                      error_message = (_('NON_UNIQUE_FIELD_NAME') % ('name', 'yum3')),
                                      error_type=constants.VALIDATION_ERROR),
                      ValidationError(item_path = ("/node1/items/yum4"),
                                      error_message = (_('NON_UNIQUE_FIELD_NAME') % ('ms_url_path', '/yum3')),
                                      error_type=constants.VALIDATION_ERROR),
                      ValidationError(item_path = ("/node1/items/yum5"),
                                      error_message = (_('NON_UNIQUE_FIELD_NAME') % ('ms_url_path', '/yum3')),
                                      error_type=constants.VALIDATION_ERROR),]
        self.assertEqual(10, len(errors))
        self.assertTrue(all(x in ref_errors for x in errors))

    def test_update_model(self):
        repo1 = MagicMock()
        repo1.name = 'yum_repo1'
        repo1.is_initial = MagicMock(return_value=False)
        repo1.is_for_removal = MagicMock(return_value=False)
        repo1.ms_url_path = '/repo1'
        repo1.get_source=MagicMock(return_value=repo1)
        def del_prop1(x):
            repo1.checksum = None
        repo1.clear_property = MagicMock(side_effect=del_prop1)
        repo3 = MagicMock()
        repo3.name = 'yum_repo2'
        repo3.is_initial = MagicMock(return_value=True)
        repo3.is_for_removal = MagicMock(return_value=False)
        repo3.ms_url_path = '/repo2'
        repo3.checksum='0x9999'
        def del_prop3(x):
            repo3.checksum = None
        repo3.clear_property = MagicMock(side_effect=del_prop3)
        repo2 = MagicMock()
        repo2.name = 'yum_repo2'
        repo2.is_initial = MagicMock(return_value=True)
        repo2.is_for_removal = MagicMock(return_value=False)
        repo2.ms_url_path = '/repo2'
        repo2.get_source=MagicMock(return_value=repo3)
        def del_prop2(x):
            repo2.checksum = None
        repo2.clear_property = MagicMock(side_effect=del_prop2)
        repos = [repo1, repo2]
        node1 = MagicMock()
        node1.is_for_removal = lambda: False
        node1.query = MagicMock(return_value=repos)
        node2 = MagicMock()
        node2.query = MagicMock(return_value=repos)
        node2.is_for_removal = lambda: False
        context_api = MagicMock()
        context_api.query = MagicMock(return_value=[node1,node2])
        open_fn = mock_open(read_data='DEADBEEF')
        with patch("__builtin__.open", open_fn):
            self.plugin.update_model(context_api)
            self.assertEqual(repo1.checksum,'7bc3a60fbf38e98f6fef654afa26d270')
            self.assertEqual(repo2.checksum,'7bc3a60fbf38e98f6fef654afa26d270')
            self.assertEqual(repo3.checksum, None)
            repo2.ms_url_path = None
            repo3.checksum = '0x7777'
            self.plugin.update_model(context_api)
            self.assertEqual(repo2.checksum, None)
            self.assertEqual(repo3.checksum, None)
        self.plugin.update_model(context_api)
        self.assertEqual(repo1.checksum, None)
        self.assertEqual(repo2.checksum, None)
        self.assertEqual(repo3.checksum, None)

    def test__validate_non_empty_checksum(self):
        repo1 = MagicMock()
        repo1.name = 'yum_repo1'
        repo1.is_initial = MagicMock(return_value=False)
        repo1.is_for_removal = MagicMock(return_value=False)
        repo1.ms_url_path = '/repo1'
        repo1.get_source=MagicMock(return_value=repo1)
        repo1.checksum = 'DEADBEEF'
        repo2 = MagicMock()
        repo2.name = 'yum_repo2'
        repo2.is_initial = MagicMock(return_value=False)
        repo2.is_for_removal = MagicMock(return_value=False)
        repo2.ms_url_path = '/repo2'
        repo2.get_source=MagicMock(return_value=repo2)
        repo2.checksum = None
        repo2.get_vpath = MagicMock(return_value='/repo2')
        repos = [repo1, repo2]
        node1 = MagicMock()
        node1.is_for_removal = lambda: False
        node1.query = MagicMock(return_value=repos)
        node2 = MagicMock()
        node2.query = MagicMock(return_value=repos)
        node2.is_for_removal = lambda: False
        context_api = MagicMock()
        context_api.query = MagicMock(return_value=[node1, node2])
        errors = self.plugin._validate_non_empty_checksum(context_api)
        # context.query mocked twice, hence the double result
        self.assertEqual(4, len(errors))
        self.assertEqual(str(errors[0]),
                '</repo2 - ValidationError - The yum repository referenced '
                'by property ms_url_path "/repo2" is not accessible. It is '
                'not possible to determine if the repository has been '
                'updated.>')

    def test_is_upgrade_flag_set_True(self):

        def mock_query(item_type):
            if item_type == 'node':
                node =  MagicMock()
                node.query = MagicMock(
                    return_value = [MagicMock(redeploy_ms='true')])
                return [node]

        api = MagicMock()
        api.query = mock_query
        result = self.plugin._is_upgrade_flag_set(api, 'redeploy_ms')
        self.assertTrue(result)

    def test_is_upgrade_flag_set_False(self):

        def mock_query(item_type):
            if item_type == 'node':
                node =  MagicMock()
                node.query = MagicMock(
                    return_value = [MagicMock(redeploy_ms='false')])
                return [node]

        api = MagicMock()
        api.query = mock_query
        result = self.plugin._is_upgrade_flag_set(api, 'redeploy_ms')
        self.assertFalse(result)
