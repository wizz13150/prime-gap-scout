"""Edit actual LOCAL launcher whitelist assignments; never execute/eval shell."""
from pathlib import Path
import contextlib,hashlib,io,os,re,shlex
from pgn_launcher import GROUPS,BOOLS,DEFAULTS,argv_from_environment,validate_coverage


class LauncherDraft:
    def __init__(self,path,parser,validate_range):
        self.path=Path(path).expanduser().resolve()
        if self.path.suffix.lower() not in ('.cmd','.sh'):raise ValueError('Choose a real local Start-PGN68.cmd or .sh')
        self.parser=parser;self.range_validator=validate_range;self.actions=validate_coverage(parser)
        self.original=self.path.read_bytes();self.digest=hashlib.sha256(self.original).hexdigest()
        self.encoding='utf-8-sig' if self.original.startswith(b'\xef\xbb\xbf') else 'utf-8'
        self.lines=self.original.decode(self.encoding).splitlines(keepends=True)
        self.values={};self.positions={};self.raw={}
        whitelist={key.upper():key for _,keys in GROUPS for key in keys}
        for index,line in enumerate(self.lines):
            stripped=line.strip()
            if self.path.suffix.lower()=='.cmd':
                match=re.fullmatch(r'(?i)set\s+"([A-Z_][A-Z_0-9]*)=([^"\r\n]*)"',stripped)
                if match is None:match=re.fullmatch(r'(?i)set\s+([A-Z_][A-Z_0-9]*)=([^\r\n]*)',stripped)
                if not match:continue
                name,value=match.groups()
            else:
                match=re.fullmatch(r'export\s+([A-Z_][A-Z_0-9]*)=(.*)',stripped)
                if not match:continue
                name,source=match.groups()
                try:parts=shlex.split(source,posix=True)
                except ValueError as error:raise ValueError('Unsupported literal assignment for '+name) from error
                if len(parts)>1:raise ValueError('Launcher value is not one literal: '+name)
                value=parts[0] if parts else ''
            name=name.upper()
            if name not in whitelist:continue
            if name in self.positions:raise ValueError('Multiple assignments for '+name+'; edit this custom script manually')
            self.positions[name]=index;self.values[name]=value;self.raw[name]=line
        missing=set(whitelist)-set(self.values)
        if missing:raise ValueError('This is not the current complete launcher schema; missing '+', '.join(sorted(missing)))
        self.initial=dict(self.values)

    def validate(self):
        for flag in BOOLS:
            if self.values[flag.upper()] not in ('0','1'):raise ValueError(flag.upper()+' must be0 or1')
        if self.values['END'] and self.values['LENGTH']:raise ValueError('Fill END or LENGTH, never both')
        for key in ('MIN_GAP','COUNT_GAP','DETAIL_GAP'):
            if self.values[key]:
                if key=='MIN_GAP' and self.values[key].strip().lower()=='auto':continue
                from decimal import Decimal,InvalidOperation
                try:value=Decimal(self.values[key])
                except InvalidOperation:raise ValueError(key+' must be an exact integer') from None
                if not value.is_finite() or value!=value.to_integral_value() or not 954<=value<=2147483647:raise ValueError(key+' must be an integer954..2147483647')
        argv=argv_from_environment(self.values)
        output=io.StringIO()
        try:
            with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):args=self.parser.parse_args(argv)
        except SystemExit as error:
            if error.code==0:return argv
            raise ValueError(output.getvalue().strip()) from None
        with contextlib.redirect_stderr(output):
            try:self.range_validator(args,self.parser)
            except SystemExit:raise ValueError(output.getvalue().strip()) from None
        if not (0<args.target_merit<float('inf')):raise ValueError('TARGET_MERIT must be finite and positive')
        return argv

    def save(self):
        self.validate()
        if hashlib.sha256(self.path.read_bytes()).hexdigest()!=self.digest:
            raise RuntimeError('Launcher changed on disk. Draft is preserved; reload before saving')
        lines=list(self.lines)
        for name,value in self.values.items():
            if value==self.initial[name]:continue
            if any(char in value for char in ('\0','\r','\n')):raise ValueError('A launcher value cannot contain a control/newline')
            old=lines[self.positions[name]]
            ending='\r\n' if old.endswith('\r\n') else '\n' if old.endswith('\n') else ''
            if self.path.suffix.lower()=='.cmd':
                if '"' in value:raise ValueError('CMD values cannot contain double quotes')
                replacement='set "'+name+'='+value+'"'
            else:replacement='export '+name+"='"+value.replace("'","'\"'\"'")+"'"
            lines[self.positions[name]]=replacement+ending
        data=''.join(lines).encode(self.encoding)
        backup=self.path.with_name(self.path.name+'.bak')
        pending=backup.with_name(backup.name+'.pending')
        with pending.open('wb') as stream:stream.write(self.original);stream.flush();os.fsync(stream.fileno())
        os.replace(pending,backup)
        pending=self.path.with_name(self.path.name+'.pending')
        with pending.open('wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(pending,self.path)
        self.original=data;self.digest=hashlib.sha256(data).hexdigest();self.lines=data.decode(self.encoding).splitlines(keepends=True);self.initial=dict(self.values)
        return backup
