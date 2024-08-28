require 'syslog'

module MCollective
  module Agent
    class Yumcache<RPC::Agent
      begin
        PluginManager.loadclass("MCollective::Util::LogAction")
        log_action = Util::LogAction
      rescue LoadError => e
        raise "Cannot load logaction util: %s" % [e.to_s]
      end

      action "clear" do
        cmd = "yum --disablerepo=* --enablerepo=#{request[:repo]} clean metadata"
        log_action.debug(cmd, request)
        reply[:status] = run("#{cmd}",
                              :stdout => :out,
                              :stderr => :err,
                              :chomp => true)
      end
    end
  end
end
