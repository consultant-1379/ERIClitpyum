class task_ms1__yumrepo__yum1(){
    yumrepo { "yum1":
        baseurl => "http://path/to/yum1",
        descr => "yum1",
        enabled => "1",
        gpgcheck => "0",
        metadata_expire => "absent",
        name => "yum1",
        skip_if_unavailable => "1"
    }
}


node "ms1" {

    class {'litp::ms_node':}


    class {'task_ms1__yumrepo__yum1':
    }


}
