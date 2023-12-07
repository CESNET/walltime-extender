Name:    openpbs-walltime-extender
Version: 1.0
Release: 7
Summary: openpbs-walltime-extender
BuildRequires: python3
Requires: python3
Requires: python3-psycopg2
Requires: python3-devel
Requires: postgresql
Requires: postgresql-server
Requires: postgresql-devel

License: Public Domain
Source0: openpbs-walltime-extender-%{version}.tar.gz

%define debug_packages %{nil}
%define debug_package %{nil} 

%description
openpbs-walltime-extender

%prep
%setup

%build

%install
install -D -m 644 openpbs-walltime-extender.service %{buildroot}%{_unitdir}/openpbs-walltime-extender.service
install -D -m 644 openpbs-walltime-extender.conf %{buildroot}/opt/pbs/etc/openpbs-walltime-extender.conf
install -D -m 744 openpbs-walltime-extender.py %{buildroot}/opt/pbs/bin/openpbs-walltime-extender.py
install -D -m 744 openpbs-walltime-extender %{buildroot}/opt/pbs/bin/openpbs-walltime-extender
install -D -m 644 _pbs_ifl.so %{buildroot}/opt/pbs/lib/python3-pbs_ifl/_pbs_ifl.so
install -D -m 644 pbs_ifl.py %{buildroot}/opt/pbs/lib/python3-pbs_ifl/pbs_ifl.py
install -D -m 644 openpbs-walltime-extender.remctl %{buildroot}/etc/remctl/conf.d/openpbs-walltime-extender

%post
%systemd_post openpbs-walltime-extender.service
if [ ! -d /opt/pbs/var/postgresql/openpbs-walltime-extender ] ; then
    mkdir -p /opt/pbs/var/postgresql
    chown postgres:postgres /opt/pbs/var/postgresql/ -R
    sudo -u postgres POSTGRESQL_PATH_HERE/initdb -D /opt/pbs/var/postgresql/openpbs-walltime-extender/
    sudo -u postgres POSTGRESQL_PATH_HERE/pg_ctl -D /opt/pbs/var/postgresql/openpbs-walltime-extender/ -o '-p 5455' start -w
    sudo -u postgres psql -h localhost -p 5455 -c 'CREATE DATABASE walltime_extender;'
    sudo -u postgres POSTGRESQL_PATH_HERE/pg_ctl -D /opt/pbs/var/postgresql/openpbs-walltime-extender/ stop -w
fi

%preun
%systemd_preun openpbs-walltime-extender.service

%postun
%systemd_postun_with_restart openpbs-walltime-extender.service

%files
/opt/pbs/bin/openpbs-walltime-extender
/opt/pbs/bin/openpbs-walltime-extender.py
/opt/pbs/lib/python3-pbs_ifl/_pbs_ifl.so
/opt/pbs/lib/python3-pbs_ifl/pbs_ifl.py
/etc/remctl/conf.d/openpbs-walltime-extender
%{_unitdir}/openpbs-walltime-extender.service
%config /opt/pbs/etc/openpbs-walltime-extender.conf
%exclude /opt/pbs/lib/python3-pbs_ifl/pbs_ifl.pyc
%exclude /opt/pbs/lib/python3-pbs_ifl/pbs_ifl.pyo

%changelog
