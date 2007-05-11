#!/usr/local/bin/perl

if (@ARGV != 1) {
	die "usage: makedist.pl <version>";
	}
$vers = $ARGV[0];

@files = ("config-*-linux",
	  "config-solaris", "images", "index.cgi", "mime.types",
	  "miniserv.pl", "os_list.txt", "perlpath.pl", "setup.sh",
	  "version", "web-lib.pl", "web-lib-funcs.pl", "README",
	  "chooser.cgi", "miniserv.pem",
	  "config-aix", 
	  "newmods.pl", "copyconfig.pl", "config-hpux", "config-freebsd",
	  "help.cgi", "user_chooser.cgi",
	  "group_chooser.cgi", "config-irix", "config-osf1", "thirdparty.pl",
	  "oschooser.pl", "config-unixware",
	  "config-openserver", "switch_user.cgi", "lang", "ulang",
	  "lang_list.txt", "usermin-init", "usermin-daemon",
	  "config-openbsd",
	  "config-macos", "LICENCE", "PATENTS",
	  "session_login.cgi", "referer_save.cgi",
	  "defaultacl", "date_chooser.cgi",
	  "install-module.pl", "LICENCE.ja",
	  "favicon.ico", "config-netbsd",
	  "defaulttheme", "feedback.cgi", "feedback_form.cgi", "usermin-pam",
	  "uconfig.cgi", "uconfig_save.cgi", "acl_security.pl", "maketemp.pl",
	  "javascript-lib.pl", "usermin-pam-osx",
	  "config-lib.pl", "entities_map.txt",
	  "password_form.cgi", "password_change.cgi", "ui-lib.pl",
	  "pam_login.cgi", "Webmin", "uptracker.cgi" );
@mlist = ("cshrc", "file", "forward", "language", "mailbox", "mscstyle3",
	  "plan", "ssh", "telnet", "theme", "gnupg", "proc", "cron",
	  "changepass", "shell", "at", "fetchmail", "quota", "mysql",
	  "procmail", "chfn", "htaccess", "commands", "man", "usermount",
	  "tunnel", "updown", "caldera", "postgresql", "spam",
	  "htaccess-htpasswd", "schedule", "mailcap", "blue-theme",
	  "filter",
	 );

chdir("/usr/local/useradmin");
system("./koi8-to-cp1251.pl");
$dir = "usermin-$vers";
system("rm -rf tarballs/$dir");
mkdir("tarballs/$dir", 0755);

# Copy top-level files to directory
print "Adding top-level files\n";
$flist = join(" ", @files);
system("cp -r -L $flist tarballs/$dir");
system("touch tarballs/$dir/install-type");
system("echo $vers > tarballs/$dir/version");

# Add module files
foreach $m (@mlist) {
	print "Adding module $m\n";
	mkdir("tarballs/$dir/$m", 0755);
	$flist = "";
	opendir(DIR, $m);
	foreach $f (readdir(DIR)) {
		if ($f =~ /^\./ || $f eq "test" || $f =~ /\.bak$/ ||
		    $f =~ /\.tmp$/ || $f =~ /\.site$/) { next; }
		$flist .= " $m/$f";
		}
	closedir(DIR);
	system("cp -r -L $flist tarballs/$dir/$m");
	}

# Update module.info and theme.info files with depends and version
opendir(DIR, "tarballs/$dir");
while($d = readdir(DIR)) {
	# set depends in module.info to this version
	local $minfo = "tarballs/$dir/$d/module.info";
	local $tinfo = "tarballs/$dir/$d/theme.info";
	if (-r $minfo) {
		local %minfo;
		&read_file($minfo, \%minfo);
		$minfo{'depends'} = join(" ", split(/\s+/, $minfo{'depends'}),
					      $vers);
		$minfo{'version'} = $vers;
		&write_file($minfo, \%minfo);
		}
	elsif (-r $tinfo) {
		local %tinfo;
		&read_file($tinfo, \%tinfo);
		$tinfo{'depends'} = join(" ", split(/\s+/, $tinfo{'depends'}),
					      $vers);
		$tinfo{'version'} = $vers;
		&write_file($tinfo, \%tinfo);
		}
	}
closedir(DIR);

# Remove useless .bak, test and other files, and create the tar.gz file
print "Creating usermin-$vers.tar.gz\n";
system("find tarballs/$dir -name '*.bak' -o -name test -o -name '*.tmp' -o -name '*.site' -o -name core -o -name .xvpics -o -name .svn | xargs rm -rf");
system("cd tarballs ; tar chf - $dir | gzip -c >usermin-$vers.tar.gz");

# Create per-module .wbm files
print "Creating modules\n";
opendir(DIR, "tarballs/$dir");
while($d = readdir(DIR)) {
	# create the module.wbm file
	local $minfo = "tarballs/$dir/$d/module.info";
	next if (!-r $minfo);
	unlink("umodules/$d.wbm", "umodules/$d.wbm.gz");
	system("(cd tarballs/$dir ; tar chf - $d | gzip -c) >umodules/$d.wbm.gz");
	}
closedir(DIR);

# Create the signature file
unlink("sigs/usermin-$vers.tar.gz-sig.asc");
system("gpg --armor --output sigs/usermin-$vers.tar.gz-sig.asc --default-key jcameron\@webmin.com --detach-sig tarballs/usermin-$vers.tar.gz");

# Create a change log for this version
$lastvers = sprintf("%.2f0", $vers - 0.005);	# round down to last stable
if ($lastvers == $vers) {
	$lastvers = sprintf("%.2f0", $vers-0.006);
	}
system("./showchangelog.pl --html $lastvers >/home/jcameron/webmin.com/uchanges-$vers.html");

# read_file(file, &assoc, [&order])
# Fill an associative array with name=value pairs from a file
sub read_file
{
open(ARFILE, $_[0]) || return 0;
while(<ARFILE>) {
        chop;
        if (!/^#/ && /^([^=]+)=(.*)$/) {
		$_[1]->{$1} = $2;
		push(@{$_[2]}, $1);
        	}
        }
close(ARFILE);
return 1;
}
 
# write_file(file, array)
# Write out the contents of an associative array as name=value lines
sub write_file
{
local($arr);
$arr = $_[1];
open(ARFILE, "> $_[0]");
foreach $k (keys %$arr) {
        print ARFILE "$k=$$arr{$k}\n";
        }
close(ARFILE);
}