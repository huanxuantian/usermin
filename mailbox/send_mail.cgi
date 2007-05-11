#!/usr/local/bin/perl
# send_mail.cgi
# Send off an email message

require './mailbox-lib.pl';

# Check inputs
&ReadParse(\%getin, "GET");
&ReadParseMime(undef, \&read_parse_mime_callback, [ $getin{'id'} ]);
&set_module_index($in{'folder'});
@folders = &list_folders();
$folder = $folders[$in{'folder'}];
&error_setup($text{'send_err'});
$in{'draft'} || $in{'to'} || &error($text{'send_eto'});
if (!$in{'subject'}) {
	if ($userconfig{'force_subject'} eq 'error') {
		&error($text{'send_esubject'});
		}
	elsif ($userconfig{'force_subject'}) {
		$in{'subject'} = $userconfig{'force_subject'};
		}
	}
@sub = split(/\0/, $in{'sub'});
$subs = join("", map { "&sub=$_" } @sub);

# Construct the email
if ($config{'edit_from'} == 2) {
	$in{'user'} || &error($text{'send_efrom'});
	$in{'from'} = $in{'dom'} ? "$in{'user'}\@$in{'dom'}" : $in{'user'};
	if ($in{'real'}) {
		$in{'from'} = "\"$in{'real'}\" <$in{'from'}>";
		}
	}
else {
	$in{'from'} || &error($text{'send_efrom'});
	}
$in{'to'} = &expand_to($in{'to'});
$in{'cc'} = &expand_to($in{'cc'});
$in{'bcc'} = &expand_to($in{'bcc'});
$newmid = "<".time().".".$$."\@".&get_system_hostname().">";
$mail->{'headers'} = [ [ 'From', $in{'from'} ],
		       [ 'Subject', $in{'subject'} ],
		       [ 'To', $in{'to'} ],
		       [ 'Cc', $in{'cc'} ],
		       [ 'Bcc', $in{'bcc'} ],
		       [ 'X-Originating-IP', $ENV{'REMOTE_ADDR'} ],
		       [ 'X-Mailer', "Usermin ".&get_webmin_version() ],
		       [ 'Message-Id', $newmid ] ];
push(@{$mail->{'headers'}}, [ 'X-Priority', $in{'pri'} ]) if ($in{'pri'});
push(@{$mail->{'headers'}}, [ 'In-Reply-To', $in{'rid'} ]) if ($in{'rid'});
if ($userconfig{'req_dsn'} == 1 ||
    $userconfig{'req_dsn'} == 2 && $in{'dsn'}) {
	push(@{$mail->{'headers'}}, [ 'Disposition-Notification-To', $in{'from'} ]);
	push(@{$mail->{'headers'}}, [ 'Read-Receipt-To', $in{'from'} ]);
	}
if ($in{'replyto'}) {
	# Add real name to reply-to address, if not given and if possible
	local $r2 = $in{'replyto'};
	local ($r2parts) = &split_addresses($r2);
	$r2 = $r2parts->[1] || !$userconfig{'real_name'} ||
		    !$remote_user_info[6] ? $in{'replyto'} :
			"\"$remote_user_info[6]\" <$r2parts->[0]>";
	push(@{$mail->{'headers'}}, [ 'Reply-To', $r2 ]);
	}
$in{'body'} =~ s/\r//g;
if ($in{'body'} =~ /\S/) {
	# Perform spell check if requested
	local $plainbody = $in{'html_edit'} ? &html_to_text($in{'body'})
					    : $in{'body'};
	if ($in{'spell'}) {
		pipe(INr, INw);
		pipe(OUTr, OUTw);
		select(INw); $| = 1; select(OUTr); $| = 1; select(STDOUT);
		if (!fork()) {
			close(INw);
			close(OUTr);
			untie(*STDIN);
			untie(*STDOUT);
			untie(*STDERR);
			open(STDOUT, ">&OUTw");
			open(STDERR, ">/dev/null");
			open(STDIN, "<&INr");
			exec("ispell -a");
			exit;
			}
		close(INr);
		close(OUTw);
		local $indent = "&nbsp;" x 4;
		local @errs;
		foreach $line (split(/\n+/, $plainbody)) {
			next if ($line !~ /\S/);
			print INw $line,"\n";
			local @lerrs;
			while(1) {
				($spell = <OUTr>) =~ s/\r|\n//g;
				last if (!$spell);
				if ($spell =~ /^#\s+(\S+)/) {
					# Totally unknown word
					push(@lerrs, $indent.&text('send_eword', "<i>".&html_escape($1)."</i>"));
					}
				elsif ($spell =~ /^&\s+(\S+)\s+(\d+)\s+(\d+):\s+(.*)/) {
					# Maybe possible word, with options
					push(@lerrs, $indent.&text('send_eword2', "<i>".&html_escape($1)."</i>", "<i>".&html_escape($4)."</i>"));
					}
				elsif ($spell =~ /^\?\s+(\S+)/) {
					# Maybe possible word
					push(@lerrs, $indent.&text('send_eword', "<i>".&html_escape($1)."</i>"));
					}
				}
			if (@lerrs) {
				push(@errs, &text('send_eline', "<tt>".&html_escape($line)."</tt>")."<br>".join("<br>", @lerrs)."<p>\n");
				}
			}
		close(INw);
		close(OUTr);
		if (@errs) {
			# Spelling errors found!
			&mail_page_header($text{'compose_title'});
			print "<b>$text{'send_espell'}</b><p>\n";
			print @errs;
			&ui_print_footer(
				"javascript:back()", $text{'reply_return'},
				"index.cgi?folder=$in{'folder'}",
				$text{'mail_return'});
			exit;
			}
		}
	local $mt = $in{'html_edit'} ? "text/html" : "text/plain";
	$mt .= "; charset=$userconfig{'charset'}";
	if ($in{'body'} =~ /[\177-\377]/) {
		# Contains 8-bit characters .. need to make quoted-printable
		$quoted_printable++;
		@attach = ( { 'headers' => [ [ 'Content-Type', $mt ],
					     [ 'Content-Transfer-Encoding',
					       'quoted-printable' ] ],
			      'data' => quoted_encode($in{'body'}) } );
		}
	else {
		# Plain 7-bit ascii text
		@attach = ( { 'headers' => [ [ 'Content-Type', $mt ],
					     [ 'Content-Transfer-Encoding',
					       '7bit' ] ],
			      'data' => $in{'body'} } );
		}
	$bodyattach = $attach[0];
	}
$attachsize = 0;
for($i=0; defined($in{"attach$i"}); $i++) {
	# Add uploaded attachment
	next if (!$in{"attach$i"});
	&test_max_attach($attachsize);
	if ($config{'max_attach'} && $attachsize > $config{'max_attach'}) {
		&error(&text('send_eattachsize', $config{'max_attach'}));
		}
	local $filename = $in{"attach${i}_filename"};
	$filename =~ s/^.*(\\|\/)//;
	local $type = $in{"attach${i}_content_type"}."; name=\"".
		      $filename."\"";
	local $disp = "inline; filename=\"".$filename."\"";
	push(@attach, { 'data' => $in{"attach${i}"},
			'headers' => [ [ 'Content-type', $type ],
				       [ 'Content-Disposition', $disp ],
				       [ 'Content-Transfer-Encoding',
					 'base64' ] ] });
	}
for($i=0; defined($in{"file$i"}); $i++) {
	# Add server-side attachment
	next if (!$in{"file$i"} || !$config{'server_attach'});
	if ($in{"file$i"} !~ /^\//) {
		$in{"file$i"} = $remote_user_info[7]."/".$in{"file$i"};
		}
	-r $in{"file$i"} && !-d $in{"file$i"} ||
		&error(&text('send_efile', $in{"file$i"}));
	local @st = stat($in{"file$i"});
	&test_max_attach($st[7]);
	local $data;
	open(DATA, "<".$in{"file$i"}) ||
		&error(&text('send_efile', $in{"file$i"}));
	while(<DATA>) {
		$data .= $_;
		}
	close(DATA);
	$in{"file$i"} =~ s/^.*\///;
	local $type = &guess_mime_type($in{"file$i"}).
		      "; name=\"".$in{"file$i"}."\"";
	local $disp = "inline; filename=\"".$in{"file$i"}."\"";
	push(@attach, { 'data' => $data,
			'headers' => [ [ 'Content-type', $type ],
				       [ 'Content-Disposition', $disp ],
				       [ 'Content-Transfer-Encoding',
					 'base64' ] ] });
	$i++;
	}

# Add forwarded attachments
@fwd = split(/\0/, $in{'forward'});
($sortfield, $sortdir) = &get_sort_field($folder);
if (@fwd) {
	@mail = &mailbox_list_mails_sorted($in{'idx'}, $in{'idx'}, $folder,
					   0, undef, $sortfield, $sortdir);
	$fwdmail = &find_message_by_index(\@mail, $folder,
					  $in{'idx'}, $in{'mid'});
	&parse_mail($fwdmail);
	&decrypt_attachments($fwdmail);

	foreach $s (@sub) {
		# We are looking at a mail within a mail ..
		&decrypt_attachments($fwdmail);
		local $amail = &extract_mail($fwdmail->{'attach'}->[$s]->{'data'});
		&parse_mail($amail);
		$fwdmail = $amail;
		}

	foreach $f (@fwd) {
		&test_max_attach(length($fwdmail->{'attach'}->[$f]->{'data'}));
		push(@attach, $fwdmail->{'attach'}->[$f]);
		}
	}

# Add forwarded emails
@mailfwdboth = split(/\0/, $in{'mailforward'});
if (@mailfwdboth) {
	@mailfwd = &messages_from_indexes($folder, \@mailfwdboth);
	foreach $fwdmail (@mailfwd) {
		local $headertext;
		foreach $h (@{$fwdmail->{'headers'}}) {
			$headertext .= $h->[0].": ".$h->[1]."\n";
			}
		push(@attach, { 'data' => $headertext."\n".$fwdmail->{'body'},
				'headers' => [ [ 'Content-type', 'message/rfc822' ],
					       [ 'Content-Description',
						  $fwdmail->{'header'}->{'subject'} ] ]
			      });
		}
	}
if ($in{'sign'} ne '' && !$in{'draft'}) {
	# Put all the attachments into a single attachment, with the signature
	# as the second attachment
	&foreign_require("gnupg", "gnupg-lib.pl");
	local @keys = &foreign_call("gnupg", "list_keys");
	$key = $keys[$in{'sign'}];

	# Create the new attachment
	push(@{$mail->{'headers'}}, [ 'Content-Type', 'multipart/signed; micalg=pgp-sha1; protocol="application/pgp-signature"' ] );
	local ($tempdata, $tempbody);
	if (@attach == 1) {
		# Just use one part
		$tempdata = &write_attachment($attach[0]);
		$tempheaders = $attach[0]->{'headers'};
		$tempbody = $attach[0]->{'data'};
		}
	else {
		# Create new attachment containing all the parts
		local $bound = "sign".time();
		foreach $a (@attach) {
			$tempbody .= "\r\n";
			$tempbody .= "--".$bound."\r\n";
			$tempbody .= &write_attachment($a);
			}
		$tempbody .= "\r\n";
		$tempbody .= "--".$bound."--\r\n";
		$tempdata ="Content-Type: multipart/mixed; boundary=\"$bound\"\r\n".
			   "\r\n".
			   $tempbody;
		$tempheaders = [ [ "Content-Type", "multipart/mixed; boundary=\"$bound\"" ] ];
		}

	# Sign the file
	local $sigdata;
	local $rv = &foreign_call("gnupg", "sign_data", $tempdata, \$sigdata,
				  $key, 2);
	if ($rv) {
		&error(&text('send_esign', $rv));
		}

	@attach = ( { 'data' => $tempbody,
		      'headers' => $tempheaders },
		    { 'data' => $sigdata,
		      'headers' => [ [ "Content-Type", "application/pgp-signature; name=signature.asc" ] ] }
		  );
	}
$mail->{'attach'} = \@attach;

if ($in{'crypt'} ne '' && !$in{'draft'}) {
	# Encrypt the entire mail
	&foreign_require("gnupg", "gnupg-lib.pl");
	local @keys = &foreign_call("gnupg", "list_keys");
	local @ekeys;
	local $key;
	if ($in{'crypt'} == -1) {
		# Find the keys for the To:, Cc: and Bcc: address
		local @addrs = ( &address_parts($in{'to'}),
				 &address_parts($in{'cc'}),
				 &address_parts($in{'bcc'}) );
		local $a;
		foreach $a (@addrs) {
			local $found;
			foreach $k (@keys) {
				if (&indexof($a, @{$k->{'email'}}) >= 0) {
					push(@ekeys, $k);
					$found++;
					last;
					}
				}
			&error(&text('send_ekey', $a)) if (!$found);
			}
		}
	else {
		@ekeys = ( $keys[$in{'crypt'}] );
		}
	if ($userconfig{'self_crypt'}) {
		local ($skey) = grep { $_->{'secret'} } @keys;
		push(@ekeys, $skey);
		}
	local $temp = &transname();
	&send_mail($mail, $temp);
	local ($tempdata, $buf);
	open(TEMP, $temp);
	local $dummy = <TEMP>;	# skip From line
	while(read(TEMP, $buf, 1024) > 0) {
		$tempdata .= $buf;
		}
	close(TEMP);
	unlink($temp);
	local $crypted;
	local $rv = &foreign_call("gnupg", "encrypt_data", $tempdata,
				  \$crypted, \@ekeys, 1);
	$rv && &error(&text('send_ecrypt', $rv));

	# Put into new attachments format
	$mail->{'headers'} =
	       [ ( grep { lc($_->[0]) ne 'content-type' } @{$mail->{'headers'}} ),
	         [ 'Content-Type',
		   'multipart/encrypted; protocol="application/pgp-encrypted"' ] ];
	$mail->{'attach'} =
		[ { 'headers' => [ [ 'Content-Transfer-Encoding', '7bit' ],
				   [ 'Content-Type', 'application/pgp-encrypted'] ],
		    'data' => "Version: 1\n" },
		  { 'headers' => [ [ 'Content-Transfer-Encoding', '7bit' ],
				   [ 'Content-Type', 'application/octet-stream' ] ],
		    'data' => $crypted }
		];
	}

# Check for text-only email
$textonly = $userconfig{'no_mime'} && !$quoted_printable &&
	    @{$mail->{'attach'}} == 1 &&
	    $mail->{'attach'}->[0] eq $bodyattach && !$in{'html_edit'};

if (!$userconfig{'send_return'}) {
	# Tell the user what is happening
	&mail_page_header($text{'send_title'});
	@tos = ( split(/,/, $in{'to'}), split(/,/, $in{'cc'}), split(/,/, $in{'bcc'}) );
	$tos = join(" , ", map { "<tt>".&html_escape($_)."</tt>" } @tos);
	print &text($in{'draft'} ? 'send_draft' : 'send_sending',
			  $tos || $text{'send_nobody'}),"<p>\n";
	}

if ($in{'draft'}) {
	# Save in the drafts folder
	($dfolder) = grep { $_->{'drafts'} } @folders;
	$qerr = &would_exceed_quota($dfolder, $mail);
	&error($qerr) if ($qerr);
	&lock_folder($dfolder);
	if ($in{'enew'} && $folder eq $dfolder) {
		# Update existing draft mail
		($dsortfield, $dsortdir) = &get_sort_field($dfolder);
		@oldmail = &mailbox_list_mails_sorted($in{'idx'}, $in{'idx'},
			       $dfolder, 0, undef, $dsortfield, $dsortdir);
		$oldmail = &find_message_by_index(\@oldmail, $dfolder, $in{'idx'}, $in{'mid'});
		$oldmail || &error($text{'view_egone'});
		&mailbox_modify_mail($oldmail, $mail, $dfolder, $textonly);
		}
	else {
		# Save as a new draft
		&write_mail_folder($mail, $dfolder, $textonly);
		}
	&unlock_folder($dfolder);
	}
else {
	# Send it off and optionally save in sent mail
	local $sfolder;
	if ($userconfig{'save_sent'}) {
		($sfolder) = grep { $_->{'sent'} } @folders;
		if ($sfolder) {
			$qerr = &would_exceed_quota($sfolder, $mail);
			&error($qerr) if ($qerr);
			}
		}
	$notify = $userconfig{'req_del'} == 1 ||
		  $userconfig{'req_del'} == 2 && $in{'del'} ?
			[ "SUCCESS","FAILURE" ] : undef;
	&send_mail($mail, undef, $textonly, $config{'no_crlf'},
		   undef, undef, undef, undef,
		   $notify);
	if ($sfolder) {
		&lock_folder($sfolder);
		&write_mail_folder($mail, $sfolder, $textonly) if ($sfolder);
		&unlock_folder($sfolder);
		}
	}

# Mark the new message as read
&open_read_hash();
if ($userconfig{'auto_mark'}) {
	$read{$newmid} ||= 1;
	}

if ($in{'abook'}) {
	# Add all recipients to the address book, if missing
	local @recips = ( &split_addresses($in{'to'}),
		    	  &split_addresses($in{'cc'}),
		    	  &split_addresses($in{'bcc'}) );
	local @addrs = &list_addresses();
	foreach $r (@recips) {
		local ($already) = grep { $_->[0] eq $r->[0] } @addrs;
		if (!$already) {
			&create_address($r->[0], $r->[1]);
			push(@addrs, [ $r->[0], $r->[1] ]);
			}
		}
	}

if ($userconfig{'send_return'}) {
	# Return to mail list
	&redirect("index.cgi?folder=$in{'folder'}");
	}
else {
	# Print footer
	print "$text{'send_done'}<p>\n";
	if ($in{'idx'} ne '') {
		&mail_page_footer(
		    "view_mail.cgi?idx=$in{'idx'}&folder=$in{'folder'}&mid=".
		    &urlize($in{'mid'})."$subs", $text{'view_return'},
		    "index.cgi?folder=$in{'folder'}", $text{'mail_return'});
		}
	else {
		&mail_page_footer(
		       "reply_mail.cgi?new=1&folder=$in{'folder'}",
				 $text{'reply_return'},
				 "index.cgi?folder=$in{'folder'}",
				 $text{'mail_return'});
		}
	}

# write_attachment(&attach)
sub write_attachment
{
local ($a) = @_;
local ($enc, $rv);
foreach $h (@{$a->{'headers'}}) {
	$rv .= $h->[0].": ".$h->[1]."\r\n";
	$enc = $h->[1]
	    if (lc($h->[0]) eq 'content-transfer-encoding');
	}
$rv .= "\r\n";
if (lc($enc) eq 'base64') {
	local $encoded = &encode_base64($a->{'data'});
	$encoded =~ s/\r//g;
	$encoded =~ s/\n/\r\n/g;
	$rv .= $encoded;
	}
else {
	$a->{'data'} =~ s/\r//g;
	$a->{'data'} =~ s/\n/\r\n/g;
	$rv .= $a->{'data'};
	if ($a->{'data'} !~ /\n$/) {
		$rv .= "\r\n";
		}
	}
return $rv;
}

sub test_max_attach
{
$attachsize += $_[0];
if ($config{'max_attach'} && $attachsize > $config{'max_attach'}) {
	&error(&text('send_eattachsize', $config{'max_attach'}));
	}
}

