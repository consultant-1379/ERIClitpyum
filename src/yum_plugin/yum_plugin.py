##############################################################################
# COPYRIGHT Ericsson AB 2013
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

import hashlib

from litp.core.plugin import Plugin
from litp.core.validators import ValidationError, OnePropertyValidator
from litp.core.execution_manager import ConfigTask,\
                                        CallbackTask,\
                                        CallbackExecutionException
from litp.core.rpc_commands import RpcCommandProcessorBase,\
                                   RpcExecutionException,\
                                   reduce_errs
from litp.core.litp_logging import LitpLogger
log = LitpLogger()

from litp.core.translator import Translator
t = Translator('ERIClitpyum_CXP9030585')
_ = t._


class YumPlugin(Plugin):
    """
    LITP yum plugin for configuration of yum repository.
    Update reconfiguration actions are supported for this
    plugin.
    """

    APACHE_DIR = "/var/www/html"
    NO_UPDATE = 0
    UPDATE_ONLY = 1
    UPDATE_AND_CLEAN = 2

    def update_model(self, plugin_api_context):
        '''
        This method is used to set the yum repository checksums before
        create_configuration is run. In case the repository is not
        present on the MS, the checksum property will be unset and
        a ValidationError will be returned by validate_model()
        '''
        self._update_yum_repo_checksum(plugin_api_context)

    def _repos_with_checksums(self, plugin_api_context):
        repos = []

        nodes = (plugin_api_context.query("node", is_for_removal=False) +
                 plugin_api_context.query("ms", is_for_removal=False))

        for node in nodes:
            repos.extend(
                [repo for repo in node.query("yum-repository",
                        is_for_removal=False) if repo.ms_url_path]
            )
        return repos

    def _unset_checksums_update(self, plugin_api_context):
        # ms_url_path and base_url are mutually exclusive
        nodes = (plugin_api_context.query("node") +
                 plugin_api_context.query("ms"))

        for node in nodes:
            for repo in node.query("yum-repository", is_for_removal=False):
                if repo.ms_url_path is None and repo.checksum is not None:
                    repo.clear_property('checksum')
                    source_item = repo.get_source()
                    if source_item.checksum is not None:
                        source_item.clear_property('checksum')

    def _update_yum_repo_checksum(self, plugin_api_context):
        self._unset_checksums_update(plugin_api_context)
        repos = self._repos_with_checksums(plugin_api_context)
        checksums_by_path = {}
        for yum_repo in repos:
            source_item = yum_repo.get_source()
            if source_item.checksum is not None:
                source_item.clear_property('checksum')
            path = yum_repo.ms_url_path
            try:
                checksum = checksums_by_path[path]
            except KeyError:
                repomd_file = YumPlugin.APACHE_DIR + \
                                path + "/repodata/repomd.xml"
                try:
                    with open(repomd_file) as rf:
                        checksum = hashlib.md5(rf.read()).hexdigest()
                    log.trace.debug('path: %s checksum: %s' % (path, checksum))
                except (IOError, OSError) as ex:
                    log.trace.error(
                        'Unable to checksum yum repository "%s", %s' %
                        (yum_repo.name, str(ex)))
                    checksum = None

                checksums_by_path[path] = checksum

            if checksum is None:
                if yum_repo.checksum:
                    yum_repo.clear_property('checksum')
            else:
                yum_repo.checksum = checksum

    def _validate_non_empty_checksum(self, plugin_api_context):
        repos = self._repos_with_checksums(plugin_api_context)
        errors = []
        for yum_repo in repos:
            if not yum_repo.checksum:
                err_msg = 'The yum repository referenced by property ' \
                'ms_url_path "%s" is not accessible. It is not possible ' \
                'to determine if the repository has been updated.' \
                % yum_repo.ms_url_path
                errors.append(ValidationError(
                    item_path=yum_repo.get_vpath(),
                    error_message=err_msg))
        return errors

    def validate_model(self, plugin_api_context):
        """
        The validation ensures that:
- The "name" property of a "yum-repository" is unique in each node.
- The "ms_url_path" property of a "yum-repository" is unique in each node.
- The "base_url" property of a "yum-repository" is unique in each node.
        """
        errors = []
        nodes = (plugin_api_context.query("node") +
                 plugin_api_context.query("ms"))

        for node in nodes:
            if not node.is_for_removal():
                item_types = node.query("yum-repository")
                opv = OnePropertyValidator(['base_url', 'ms_url_path'])
                errors.extend(self._ensure_unique('name', item_types))
                errors.extend(self._ensure_unique('base_url', item_types))
                errors.extend(self._ensure_unique('ms_url_path', item_types))
                for item in item_types:
                    err = opv.validate(item.properties)
                    if err:
                        err.item_path = item.get_vpath()
                        errors.append(err)
        errors.extend(self._validate_non_empty_checksum(plugin_api_context))
        return errors

    def _ensure_unique(self, field, item_types):
        errors = []
        namekeys = {}
        duplicatekeys = {}
        for f in item_types:
            name = getattr(f, field)
            if name is not None and namekeys.get(name):
                err_msg = _("NON_UNIQUE_FIELD_NAME") % (field, name)
                errors.append(ValidationError(
                    item_path=f.get_vpath(),
                    error_message=err_msg))
                duplicatekeys[name] = f.get_vpath()
            else:
                namekeys[name] = f.get_vpath()

        for name in namekeys.keys():
            if name in duplicatekeys.keys():
                err_msg = _("NON_UNIQUE_FIELD_NAME") % (field, name)
                errors.append(ValidationError(
                    item_path=namekeys[name],
                    error_message=err_msg))
        return errors

    @staticmethod
    def _is_upgrade_flag_set(api_context, flag):
        """
        Check if a specific upgrade flag is set
        e.g redeploy_ms which will trigger
        the generation of MS based tasks only.
        ie. LMS Redeploy Plan for RH6 Plan in RH7 Uplift.
        :param api_context: Plugin API context
        :type api_context: class PluginApiContext
        :param flag: Upgrade flag
        :type flag: string
        :return: True if flag is set on an upgrade item , else False
        :rtype: boolean
        """
        if api_context and any(
            [True for node in api_context.query('node')
             for upgrd_item in node.query('upgrade')
             if getattr(upgrd_item, flag, 'false') == 'true']):
            log.trace.info('Upgrade flag {0} is true.'.format(flag))
            return True
        else:
            return False

    def create_configuration(self, plugin_api_context):
        """
        Provides support for configuring a yum repository.

        *Some examples of configuring a yum repository follow:*

        .. code-block:: bash

            # Configuring a external 'http' yum repository
            litp create -t yum-repository -p /software/items/yum_repo1 -o \
name="yum_repo1" base_url="http://example.com/yum_repo"
            litp inherit -p \
/deployments/dep1/clusters/cluster1/nodes/node1/items/yum1 -s \
/software/items/yum_repo1

            # Configuring a local 'file' yum repository
            litp create -t yum-repository -p /software/items/yum_repo1 -o \
name="yum_repo1" base_url="file:///path/to/yum/repo"
            litp inherit -p \
/deployments/dep1/clusters/cluster1/nodes/node1/items/yum1 -s \
/software/items/yum_repo1

            # Configuring a local yum repository hosted on MS \
(available at 'http://<MS_HOSTNAME>/yum_repo1')
            litp create -t yum-repository -p /software/items/yum_repo2 -o \
name="yum_repo2" ms_url_path="/yum_repo1
            litp inherit -p \
/deployments/dep1/clusters/cluster1/nodes/node1/items/yum2 -s \
/software/items/yum_repo2

        For more information, see \
"Manage Yum Repository Client Configuration" \
from :ref:`LITP References <litp-references>`.

        """

        tasks = []
        lms_redeploy = YumPlugin._is_upgrade_flag_set(
            plugin_api_context, 'redeploy_ms')
        nodes = []
        if lms_redeploy:
            nodes = plugin_api_context.query("ms")
        else:
            nodes = (plugin_api_context.query("node") +
                     plugin_api_context.query("ms"))
        ms = plugin_api_context.query("ms")[0]
        for node in nodes:
            repos = node.query("yum-repository")

            self._add_new_repo_tasks(ms, node, repos, tasks)
            self._add_updated_repo_tasks(ms, node, repos, tasks)

        return tasks

    def _add_new_repo_tasks(self, ms, node, repos, tasks):
        added = [r for r in repos if r.is_initial()]
        tasks.extend([self._new_repo_task(ms, node, r) for r in added])

    def _item_updated_except(self, the_item, except_properties):
        ''' Return true if an item is updated except ignored properties.
            @param: QueryItem to be checked
            @param: list of ignored properties
        '''
        # LITPCDS-12023 - this method has been copied-and-pasted from
        # ERIClitppackage.  The Plugin API should provide a method that would
        # replace this.

        # avoid O(n^2) because applied_properties contains a `for` loop inside

        return any(self.__item_updated_summary(the_item,
                        lambda p: p not in except_properties))

    def _item_updated_only(self, the_item, only_properties):
        return any(self.__item_updated_summary(the_item,
                        lambda p: p in only_properties))

    def __item_updated_summary(self, the_item, condition):
        applied_props = the_item.applied_properties
        summary = []
        for prop_name in the_item.properties:
            try:
                if getattr(the_item, prop_name) == applied_props[prop_name]:
                    continue
            except KeyError:
                pass
            if condition(prop_name):
                summary.append(prop_name)
        return summary

    def _requires_update(self, repo, node):
        if repo.is_updated():
            if self._item_updated_except(repo, ['checksum']):
                if self._item_updated_only(repo, ['ms_url_path', 'base_url']):
                    return YumPlugin.UPDATE_AND_CLEAN
                return YumPlugin.UPDATE_ONLY
        elif all((repo.ms_url_path,
                  node.is_updated(),
                  node.hostname != node.applied_properties.get('hostname'))):
            return YumPlugin.UPDATE_ONLY
        return YumPlugin.NO_UPDATE

    def _add_updated_repo_tasks(self, ms, node, repos, tasks):
        updated = [(r, self._requires_update(r, node)) for r in repos]
        for u, ru in updated:
            if ru == YumPlugin.NO_UPDATE:
                continue
            repo_task = self._new_repo_task(ms, node, u)
            tasks.append(repo_task)
            if ru == YumPlugin.UPDATE_AND_CLEAN:
                clean_task = self._clean_metadata_task(u, node, u)
                clean_task.requires.add(repo_task)
                tasks.append(clean_task)

    def _requires_removal(self, repo):
        if repo.is_for_removal():
            return True
        return False

    def _new_repo_task(self, ms, node, repo):
        props = self.get_properties(ms, repo)
        props["skip_if_unavailable"] = "1"
        operation = ""
        if repo.is_initial():
            operation = 'Add yum repository "%s" on node "%s"' % (
                repo.name, node.hostname)
        elif repo.is_updated():
            operation = 'Update yum repository "%s" on node "%s"' % (
                repo.name, node.hostname)
        task = ConfigTask(
            node=node,
            model_item=repo,
            description=operation,
            call_type="yumrepo",
            # call_id=repo.name,
            call_id=repo.properties.get('name'),
            **props
        )
        if repo.get_source():
            task.model_items.add(repo.get_source())
        return task

    def _clean_metadata_task(self, model_item, node, repo):
        task = CallbackTask(
            model_item,
            'Clean metadata for yum repository "{0}" on node "{1}"'.format(
                repo.name, node.hostname),
            self._clean_metadata_callback,
            node.hostname,
            repo.name
        )
        if model_item.get_source():
            task.model_items.add(model_item.get_source())
        return task

    def _clean_metadata_callback(self, callback_api, node_hostname, repo):
        try:
            bcp = RpcCommandProcessorBase()
            _, errors = bcp.execute_rpc_and_process_result(
                callback_api,
                [node_hostname],
                'yumcache',
                'clear',
                {'repo': repo},
                timeout=60
            )
        except RpcExecutionException as e:
            raise CallbackExecutionException(e)
        if errors:
            raise CallbackExecutionException(','.join(reduce_errs(errors)))

    def get_properties(self, node, repo):
        props = {
            "gpgcheck": "0",
            "enabled": "1",
            "name": repo.name,
            "descr": repo.name,
        }
        properties = repo.properties

        baseurl = properties.get('base_url')
        if baseurl is None:
            baseurl = properties.get('ms_url_path')
            baseurl = "http://{0}{1}".format(node.hostname, baseurl)
        props["baseurl"] = baseurl

        if properties.get("cache_metadata") == 'false':
            props["metadata_expire"] = "0"
        else:
            props["metadata_expire"] = "absent"
        return props
