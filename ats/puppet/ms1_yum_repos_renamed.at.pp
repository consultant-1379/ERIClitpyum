class task_ms1__file___2fetc_2fyum_2erepos_2ed_2fyum1_2erepo(){
    file { "/etc/yum.repos.d/yum1.repo":
        ensure => "absent"
    }
}

class task_ms1__yumrepo__yum1(){
    yumrepo { "yum1":
        baseurl => "http://path/to/yum1",
        enabled => "1",
        gpgcheck => "0",
        metadata_expire => "0",
        name => "yum1",
        skip_if_unavailable => "1"
    }
}

class task_ms1__yumrepo__yumnew(){
    yumrepo { "yumnew":
        baseurl => "http://path/to/yum1",
        enabled => "1",
        gpgcheck => "0",
        metadata_expire => "0",
        name => "yumnew",
        skip_if_unavailable => "1"
    }
}


node "ms1" {

    class {'litp::ms_node':}


    class {'task_ms1__file___2fetc_2fyum_2erepos_2ed_2fyum1_2erepo':
    }


    class {'task_ms1__yumrepo__yum1':
    }


    class {'task_ms1__yumrepo__yumnew':
    }


}