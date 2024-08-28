class task_ms1__package__mock_2dpackage_2erpm(){
    package { "mock-package.rpm":
        ensure => "installed"
    }
}

class task_ms1__yumrepo__yum1(){
    yumrepo { "yum1":
        baseurl => "http://path/to/yum1",
        descr => "yum1",
        enabled => "1",
        gpgcheck => "0",
        metadata_expire => "0",
        name => "yum1",
        skip_if_unavailable => "1"
    }
}

class task_ms1__yumrepo__yum2(){
    yumrepo { "yum2":
        baseurl => "http://path/to/yum2",
        descr => "yum2",
        enabled => "1",
        gpgcheck => "0",
        metadata_expire => "0",
        name => "yum2",
        skip_if_unavailable => "1"
    }
}


node "ms1" {

    class {'litp::ms_node':}


    class {'task_ms1__package__mock_2dpackage_2erpm':
    }


    class {'task_ms1__yumrepo__yum1':
    }


    class {'task_ms1__yumrepo__yum2':
    }


}