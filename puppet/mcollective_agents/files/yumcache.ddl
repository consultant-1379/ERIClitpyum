metadata :name        => "yumcache",
         :description => "Agent to clear LITP yumrepo cache",
         :author      => "Ericsson AB",
         :license     => "Ericsson",
         :version     => "1.0",
         :url         => "http://ericsson.com",
         :timeout     => 300

action "clear", :description => "Clear cache for a yumrepo" do
    display :always

    input :repo,
          :prompt      => "yumrepo",
          :description => "The yumrepo to clear cache",
          :type        => :string,
          :validation  => '^[a-zA-Z0-9\-\._]+$',
          :optional    => false,
          :maxlength   => 250 # RHEL maximum filesize length

    output :status,
           :description => "The output of the command",
           :display_as  => "Command result",
           :default     => "no output"
end
