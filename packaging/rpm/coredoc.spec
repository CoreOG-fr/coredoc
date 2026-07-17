Name:           coredoc
Version:        0.2.0
Release:        1%{?dist}
Summary:        Modular TUI-based Linux diagnostics and first-aid tool
License:        MIT
URL:            https://github.com/CoreOG-fr/coredoc
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
Requires:       python3-textual

%description
coredoc wraps fragmented Linux diagnostic tools into a coherent Textual TUI
that explains what is broken and what to check next.

%prep
%autosetup

%build
%py3_build

%install
%py3_install
install -Dm0644 man/coredoc.1 %{buildroot}%{_mandir}/man1/coredoc.1

%files
%license README.md
%doc docs/ARCHITECTURE.md docs/TRIAGE.md docs/SECURITY.md
%{_bindir}/coredoc
%{python3_sitelib}/coredoc*
%{_mandir}/man1/coredoc.1*

%changelog
* Thu Jul 16 2026 coredoc contributors <noreply@users.noreply.github.com> - 0.2.0-1
- Initial package
