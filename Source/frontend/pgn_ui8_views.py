"""Pure UI8 projections. Current controlled job and selected saved result differ."""
from decimal import Decimal
from rich import box
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def sci(value):
    try:
        number=int(value)
        if not number:return '0'
        sign='-' if number<0 else '';digits=str(abs(number));tail=digits[1:].rstrip('0')
        return sign+digits[0]+('.'+tail if tail else '')+'e'+str(len(digits)-1)
    except (ValueError,TypeError):return '--'


def range_text(start,end):return f'{sci(start)} → {sci(end)}'


def length_text(value):
    return sci(value)


def gpu_short(value):
    return str(value or '--').replace('NVIDIA','').replace('GeForce','').strip().replace('RTX ','RTX').replace('GTX ','GTX')


def date_short(value):return str(value or '--').replace('T',' ')[:16]


def summary(context):
    table=Table.grid(expand=True,padding=(0,1));table.add_column(width=19,style='dim');table.add_column()
    active=context.get('active_session')
    selected=context.get('selected_session')
    if active:
        status='Running' if active.get('job_active') else {'PAUSED':'Paused','COMPLETE':'Complete','FAILED':'Failed'}.get(active.get('status'),'Idle')
        table.add_row(status,Text(range_text(active.get('start'),active.get('end')),style='bold white'))
    if not active:table.add_row('',Text('Idle',style='cyan'))
    next_range=context.get('next_range') or (active or {}).get('next_range')
    if next_range:
        config=next_range.get('configuration',next_range)
        table.add_row('NEXT '+str(next_range.get('resolved_status',next_range.get('status','saved'))),Text(range_text(config.get('start'),config.get('end')),style='yellow'))
    return table


def page(title,body,context,footer):
    active=context.get('active_session') or {}
    status='WIZZ • saved sessions · read only' if context.get('browser_only') else 'Running' if active.get('job_active') else {'PAUSED':'Paused','COMPLETE':'Complete','FAILED':'Failed'}.get(str(context.get('status','')).upper(),'Idle')
    heading=Table.grid(expand=True);heading.add_column();heading.add_column(justify='right')
    heading.add_row(Text('PGN 68 > '+title,style='bold white'),Text(status,style='cyan'))
    layout=Layout()
    parts=[Layout(Panel(heading,box=box.ROUNDED,border_style='cyan',padding=(0,1)),size=3)]
    if title in ('Menu','Search ranges'):
        parts.append(Layout(Panel(summary(context),box=box.SIMPLE,padding=(0,0)),size=4 if context.get('next_range') else 3))
    parts.extend((Layout(body,ratio=1),Layout(Panel(Text('[Esc Back]  '+footer,style='white'),box=box.ROUNDED,border_style='cyan',padding=(0,1)),size=3)))
    layout.split_column(*parts)
    return layout


def render_main(context):
    table=Table.grid(expand=True,padding=(0,1));table.add_column(width=3,style='bold cyan');table.add_column()
    focus=context.setdefault('_ui_state',{}).get('main_focus',0)
    for index,(number,title,hint) in enumerate((('1','Search ranges','New range or queue NEXT; edit parameters and the local launcher.'),
                              ('2','My sessions','Automatically found actual saved sessions: view COMPLETE, resume supported interruptions.'),
                              ('3','Result folders','Saved result folders by session. Enter opens the folder.'))):
        style='on #12334b' if index==focus else ''
        table.add_row(('›' if index==focus else '')+number,Text(title,style='bold white'),style=style);table.add_row('',Text(hint,style='dim'),style=style)
    return page('Menu',Panel(table,box=box.SIMPLE,padding=(0,1)),context,'↑↓ Select · Enter Open · 1/2/3/4 Open directly')


def render_search(context,draft,error=None):
    table=Table.grid(expand=True,padding=(0,1));table.add_column(width=22,style='dim');table.add_column()
    for key,label in (('start','Prepared start'),('length','Prepared length'),('end','Prepared end (AUTO)'),('min_gap','MIN_GAP'),('gpu','Selected GPU index'),('bins','Count bins'),('report_top','Human report top'),('target_merit','Display merit goal')):
        value=draft.get(key,'')
        if key in ('start','end'):value=sci(value)
        elif key=='length':value=length_text(value)
        table.add_row(label,str(value))
    if error:table.add_row('Status',Text(str(error),style='cyan'))
    table.add_row('Local launcher',Text(str(context.get('launcher_path','Not selected')),style='cyan'))
    label='Prepare NEW / NEXT only: no GPU launch in this browser.' if context.get('browser_only') else 'NEW explicitly changes session; NEXT finishes current first.'
    body=Group(table,Text(label,style='yellow'))
    return page('Search ranges',body,context,'1 NEW form · 2 NEXT form · L Local launcher settings')


def render_arrow_list(title,entries,selected,offset,total,context,footer):
    table=Table.grid(expand=True,padding=(0,1));table.add_column(width=3);table.add_column()
    for index,entry in enumerate(entries):
        focused=(offset+index)==selected
        label=Text(str(entry.get('label','')),style='bold white' if focused else 'white',no_wrap=True,overflow='ellipsis')
        path=entry.get('path')
        if path:
            try:label.stylize('link '+__import__('pathlib').Path(path).resolve().as_uri())
            except ValueError:pass
        detail=Text(str(entry.get('detail','')),style='white' if focused else 'dim',no_wrap=True,overflow='ellipsis')
        table.add_row(Text('›' if focused else '',style='cyan'),Group(label,detail),style='on #12334b' if focused else '')
    if not entries:table.add_row('','No saved sessions found in these result folders.')
    count=Text(f'Item {selected+1 if total else 0} / {total} · showing {offset+1 if total else 0}–{min(total,offset+len(entries))}',style='dim')
    return page(title,Group(table,count),context,footer)


def render_report(lines,selected,offset,total,context):
    text=Text('\n'.join(lines),style='white',no_wrap=True,overflow='ellipsis')
    return page('Actual saved results',Group(text,Text(f'Line {selected+1}/{total}',style='dim')),context,
                '↑↓ Scroll · PgUp/PgDn/Home/End · F Open folder')


def render_details(session,context):
    info=session.context();table=Table.grid(expand=True,padding=(0,1));table.add_column(width=22,style='dim');table.add_column()
    for name,value in (('Saved status',info['status']),('Origin',info['host']),('Session',info['session_id'][:8]),('Actual GPU',gpu_short(info['gpu_name'])),
                       ('Created UTC',date_short(info['created_utc'])),('Counted gaps',info['counted_gaps']),('Local folder',info['folder'])):
        table.add_row(name,str(value))
    table.add_row('Range',range_text(info['start'],info['end']))
    table.add_row('Completed positions',length_text(info['position']))
    note='Read-only WIZZ mirror. Saved '+info['status']+'; no worker is active here.' if session.readonly_mirror else 'The backend verifies immutable worker/GPU/filter bindings before resume.'
    return page('Session',table,context,'Enter '+str(context.get('_session_primary_action','View report'))+' · R Open results · C Counts CSV',note=note)


def render_form(title,fields,focused=0,error=None,preview=None):
    preview=preview or {};context=preview.get('context',{})
    table=Table.grid(expand=True,padding=(0,1));table.add_column(width=3);table.add_column(width=24);table.add_column()
    for index,(name,label,value,hint) in enumerate(fields):
        table.add_row('›' if index==focused else '',Text(str(label),style='white'),Text(str(value) or '—',style='bold white' if index==focused else 'dim'),style='on #12334b' if index==focused else '')
    hint=str(fields[focused][3]) if fields else ''
    lines=[table,Text(hint,style='cyan')]
    if error:lines.append(Text(str(error),style='red'))
    return page(title,Group(*lines),context,'Tab/↑↓ Field · Enter Validate · Ctrl+U Clear · Esc cancels from any field')


def render_launcher(context,path,rows,selected,offset,total,error=None,advanced=False):
    table=Table.grid(expand=True,padding=(0,1));table.add_column(width=3);table.add_column(width=22);table.add_column()
    for index,row in enumerate(rows):
        table.add_row('›' if offset+index==selected else '',Text(row['variable'],style='bold white'),Text(row['value'] or '(blank / inherit)',style='cyan'),style='on #12334b' if offset+index==selected else '')
    lines=[Text('LOCAL file: '+str(path),style='cyan'),Text('Explicit Save changes the NEXT launch only. Current session stays immutable.',style='dim'),table]
    if rows and 0<=selected-offset<len(rows):lines.append(Text(str(rows[selected-offset].get('help','')),style='cyan'))
    if error:lines.append(Text(str(error),style='red'))
    lines.append(Text(f'{selected+1 if total else 0}/{total} · Advanced '+('expanded' if advanced else 'collapsed'),style='dim'))
    return page('Search ranges > Local launcher settings',Group(*lines),context,'↑↓ Select · Enter Edit · A Advanced · S Save + .bak · Esc Back (draft retained)')

import shutil

BG='#102b3a'
MUTED='grey58'
COLORS={'Starting':'yellow','Searching':'cyan','Processing':'cyan','Current':'cyan','Ready':'white','Suspended':'blue','Pausing':'yellow','Stopping':'yellow','Complete':'green','Running':'cyan','Paused':'blue','Queued':'yellow','Pending':'yellow','Draft':'white','Failed':'red'}


def _hovered(key, target='footer', index=None):
    try:
        from pgn_terminal_input import get_hover_region
        region = get_hover_region()
        return bool(region and region.target == target and region.key == key and
                    (index is None or region.index == index))
    except (ImportError, AttributeError):
        return False


def _button(label,shortcut,key,target='footer',index=None,enabled=True,compact=False):
    """One painter is shared by menu/form/mining, including disabled controls."""
    hover=_hovered(key,target,index)
    background=('#26323b'if hover else'#18242b')if not enabled else'bright_blue'if hover else'#16415b'
    foreground='grey50'if not enabled else'bold white'
    text=Text(''if compact else' ',style='on '+background)
    text.append(str(label),foreground+' on '+background)
    text.append((''if compact else' ')+'['+str(shortcut)+']'+(''if compact else' '),
                ('grey50'if not enabled else'bold bright_cyan')+' on '+background)
    return text

def _footer_specs(footer):
    mapping = {'C':('c','C'), 'N':('n','N'), 'E':('e','E'), 'R':('r','R'),
               'V':('v','V'), 'G':('g','G'), 'A':('a','A'), 'T':('t','T'),
               'S':('s','S'), 'L':('l','L'), 'F':('f','F'), 'Y':('y','Y'),
               'P':('p','P'), 'M':('m','M'), 'Q':('q','Q'), 'Ctrl+C':('\x03','Ctrl+C'), 'Ctrl+S':('SAVE','Ctrl+S'),
               'Ctrl+U':('CLEAR','Ctrl+U'), 'Delete':('DELETE','Del'),
               'Del':('DELETE','Del'), 'Enter':('ENTER','Enter'),
               'Enter/E':('ENTER','Enter'), 'Esc':('ESC','Esc')}
    specs = [('Back','Esc','ESC')]
    help_items = []
    for raw in str(footer).split(' · '):
        token, _, label = raw.strip().partition(' ')
        binding = mapping.get(token)
        if binding:
            key, shortcut = binding
            if key == 'ESC':
                continue
            specs.append((label or token, shortcut, key))
        elif raw.strip() and raw.strip() not in ('1/2/3 Open','1/2/3 Open directly'):
            help_items.append(raw.strip())
    return specs, ' · '.join(help_items)


def _footer(footer,width,height,include_back=True):
    from rich.cells import cell_len
    disabled=set()
    if isinstance(footer,(list,tuple)):
        specs=[(item['label'],item.get('shortcut',''),item['key'])for item in footer]
        disabled={item['key']for item in footer if not item.get('enabled',True)}
        help_text=''
        if include_back and not any(key=='ESC'for _,_,key in specs):specs.insert(0,('Back','Esc','ESC'))
    else:
        specs,help_text=_footer_specs(footer)
        if not include_back:specs=[s for s in specs if s[2]!='ESC']
    specs=[('Launcher'if label=='Launcher settings'else label,shortcut,key)for label,shortcut,key in specs]
    aliases={'Save range':'Save','Save launcher':'Launcher','Apply pending edit':'Apply','Advanced':'More','Launcher':'File','Start':'Start',
             'Switch to range':'Switch','Switch to queued':'Switch','Switch & resume':'Resume','Start queued':'Start','Open progress':'Progress',
             'Start recording':'Record','Stop recording':'Stop','Open folder':'Folder','Open results':'Results','Open archive':'ZIP'}
    selected=None;available=max(1,width-4)
    for mode in range(4):
        buttons=[]
        for label,shortcut,key in specs:
            if mode>=2:label=aliases.get(label,label)
            buttons.append((_button(label,shortcut,key,enabled=key not in disabled,compact=mode>0),key))
        gap=0 if mode==3 else 1
        if sum(cell_len(b.plain)for b,k in buttons)+gap*max(0,len(buttons)-1)<=available:selected=(buttons,gap);break
    if selected is None:
        selected=([(_button('Back','Esc','ESC'),'ESC')],1);help_text='Widen the terminal to show every action.'
    buttons,gap=selected;line=Text();regions=[];x=0
    for button,key in buttons:
        if x:line.append(' '*gap);x+=gap
        count=cell_len(button.plain)
        regions.append(dict(x=2+x,y=height-2,width=count,height=1,key=key,target='footer',painted=button.plain,disabled=key in disabled))
        line.append_text(button);x+=count
    return Panel(line,box=box.ROUNDED,border_style='cyan',padding=(0,1)),3,regions,help_text

def _body_text_regions(body, width, needles, target, start_y=3):
    """Locate row controls from the exact Rich projection, not byte offsets."""
    from rich.cells import cell_len
    from rich.console import Console
    console = Console(width=width)
    lines = console.render_lines(body, console.options, pad=False)
    regions = []
    for label, key, index, row_height in needles:
        for y, segments in enumerate(lines):
            line = ''.join(segment.text for segment in segments)
            found = line.find(label)
            if found >= 0:
                regions.append(dict(x=cell_len(line[:found]), y=start_y+y,
                    width=cell_len(label), height=row_height,
                    key=key, target=target, index=index))
                break
    return regions


def _progress(context, width):
    active = context.get('active_session') or {}
    status = _status(context)
    if status == 'Idle':
        return Text('')
    try:
        total = int(active['end']) - int(active['start'])
        position = int(active.get('position',0))
        if total <= 0 or not 0 <= position <= total:
            raise ValueError
    except (ValueError, TypeError, KeyError):
        return Panel(Text('Progress is not available yet.', style='grey70'),
            title='Current search · ' + status, title_align='left',
            border_style=COLORS.get(status,'cyan'), box=box.ROUNDED, padding=(0,1))
    columns = max(10, width-6)
    done = position * columns // total
    color = COLORS.get(status,'cyan')
    bar = Text('█'*done, style=color)
    bar.append('░'*(columns-done), style='grey35')
    return Panel(Group(Text(f'{100*position/total:.2f}% completed',style='bold white'),bar),
        title='Current search · ' + status, title_align='left',
        border_style=color, box=box.ROUNDED,padding=(0,1))


def render_diagnostics(context, state, message=None):
    """Project only recorder-reported facts; never sample hardware here."""
    state = state or {}
    recording = bool(state.get('recording'))
    lines = [Text.assemble(('Status: ','grey70'),
             (str(state.get('status','Stopped')),'bold cyan' if recording else 'bold white'))]
    if recording:
        lines.extend((Text('Recording quietly in the background.',style='white'),
                      Text('You can leave this page and continue using PGN.',style='grey70')))
    else:
        summary = state.get('summary') or {}
        if summary:
            duration = summary.get('duration_seconds')
            if isinstance(duration,(int,float)) and duration >= 0:
                duration_text = f'{duration:.1f} sec'
            else:
                duration_text = 'Not available'
            lines.append(Text.assemble(('Duration: ','grey70'),(duration_text,'white'),
                                       ('   Samples: ','grey70'),(str(summary.get('samples',0)),'white')))
            categories = (('Recorded','recorded','green'),('Partly available','partial','yellow'),
                          ('Unavailable','unavailable','yellow'),('Not collected','not_collected','grey70'))
            for label,key,color in categories:
                values = summary.get(key) or []
                if values:
                    lines.append(Text.assemble((label+': ',color),(', '.join(map(str,values)),'white')))
                elif key == 'recorded':
                    lines.append(Text('Recorded: No categories were collected.',style='yellow'))
            if summary.get('missing_files'):
                lines.append(Text('Missing files: '+', '.join(map(str,summary['missing_files'])),style='yellow'))
            if summary.get('errors'):
                lines.append(Text('Collection issues: '+'; '.join(map(str,summary['errors'])),style='yellow'))
        else:
            lines.append(Text('Start a local recording, then stop it to prepare a report.',style='grey70'))
        archive = state.get('archive_path')
        archive_status = str(state.get('archive_status','Not created'))
        if archive:
            color = 'green' if archive_status == 'Ready' else 'yellow'
            lines.append(Text('ZIP ready to send' if archive_status == 'Ready' else 'ZIP: '+archive_status,style='bold '+color))
            lines.append(Text(str(archive),style='cyan',overflow='fold'))
            members=state.get('archive_files') or []
            if members:
                lines.append(Text('Contents: '+str(len(members))+' files · '+str(state.get('archive_bytes','?'))+' bytes',style='white'))
                lines.append(Text(', '.join(str(item['path']) for item in members),style='grey70',overflow='fold'))
            else:lines.append(Text('Contents summary unavailable; inspect DIAGNOSTIC-MANIFEST.json in the archive.',style='yellow'))
        elif archive_status not in ('Not created','Recording'):
            lines.append(Text('ZIP: '+archive_status,style='yellow'))
    if state.get('error'):
        lines.append(Text(str(state['error']),style='red'))
    lines.append(Text('Local report only. Nothing is uploaded automatically.',style='grey58'))
    body = Panel(Group(*lines),title='Local recording' if recording else 'Recording summary',
                 title_align='left',border_style=MUTED,box=box.ROUNDED,padding=(0,1))
    return page('Developer diagnostics',body,context,
                'S Start recording · T Stop recording · R Open folder',
                note=message,note_height=1)


def _status(context):
    from pgn_ui_workflow import phase
    return phase(context).replace('_',' ').title()

def _size(context):
    from pgn_terminal_input import terminal_size
    value=terminal_size(fallback=(120,34))
    return int(context.get('_view_width',value.columns)),int(context.get('_view_height',value.lines))

def _workspace(context):return context.get('workspace') or {}

def _cards(context):return _workspace(context).get('cards',[])

def _range_bar(cards,lower,upper,width,focus=None):
    width=max(1,int(width));glyphs=['░']*width;styles=['grey35']*width
    if upper<=lower:return Text('░'*width,style='grey35')
    span=upper-lower
    order=sorted(cards,key=lambda c:({'saved':0,'current':1,'queued':2,'draft':3}.get(c.get('kind'),0),c.get('id')==focus))
    for card in order:
        start=max(lower,int(card['start']));end=min(upper,int(card['end']))
        if start>=end:continue
        left=min(width-1,(start-lower)*width//span);right=min(width,((end-lower)*width+span-1)//span)
        color=COLORS.get(str(card.get('status','')).title(),'white')
        for col in range(left,max(left+1,right)):
            glyphs[col]='█';styles[col]=color
        if card.get('position') and str(card.get('status','')).title()!='Complete':
            done=min(end,int(card['start'])+int(card['position']));stop=max(left,min(width,(done-lower)*width//span))
            for col in range(left,stop):styles[col]='green'
        if card.get('id')==focus:styles[left]='bold '+color
    line=Text()
    for glyph,style in zip(glyphs,styles):line.append(glyph,style)
    return line


def _range_overview(context,columns=68):
    work=_workspace(context);domain=work.get('supported_window') or {'lower':(10<<64)+20,'upper_exclusive':(11<<64)-4*1006632960}
    lower,upper=int(domain['lower']),int(domain['upper_exclusive']);cards=_cards(context);zoom=work.get('zoom')
    rows=[Text.assemble((sci(lower),'grey70'),('  →  ',MUTED),(sci(upper),'grey70')),
          _range_bar(cards,lower,upper,columns,(zoom or {}).get('focus'))]
    if zoom:
        rows += [Text.assemble(('Zoom  ','cyan'),(range_text(zoom['lower'],zoom['upper']),'white')),
                 _range_bar(cards,int(zoom['lower']),int(zoom['upper']),columns,zoom.get('focus'))]
    rows.append(Text.assemble(('█ Complete  ','green'),('█ Running  ','cyan'),('█ Paused  ','blue'),('█ Queued  ','yellow'),('█ Ready','white')))
    return Panel(Group(*rows),title='67–80-bit range map',title_align='left',border_style=MUTED,box=box.ROUNDED,padding=(0,1))


def _card(card,selected=False,index=None):
    from pgn_ui_workflow import category
    state=category(card);color=COLORS.get(state,'white')
    size=int(card['end'])-int(card['start']);position=int(card.get('position',0));percent=100*position/size if size else 0
    raw=str(card.get('backend_status',card.get('status',''))).replace('_',' ').title()
    title=Text.assemble((state,'bold '+color),(' · '+raw if raw.lower()not in(state.lower(),'ready','draft')else'','grey78'),(' · '+length_text(size),'white'))
    if card.get('kind')=='current'or card.get('can_resume'):title.append(' · '+f'{percent:.1f}%',style='white')
    cfg=card.get('configuration')or{}
    title.append(' · profile '+str(cfg.get('profile','auto')),style='grey70')
    from pgn_threshold_policy import safe_view
    threshold=safe_view(cfg,card['start'],card['end'],int(card['start'])+position)
    title.append(' · '+threshold['requested'],style='grey70')
    line=Text(range_text(card['start'],card['end']),no_wrap=True,overflow='ellipsis')
    hovered=_hovered('SELECT','workspace',index)
    return Panel(line,title=title,title_align='left',border_style='bright_cyan'if hovered else'cyan'if selected else color,
                 box=box.ROUNDED,padding=(0,1),height=3)

def page(title,body,context,footer,note=None,note_height=2):
    width,height=_size(context)
    heading=Table.grid(expand=True);heading.add_column(ratio=1);heading.add_column(justify='right')
    status=_status(context)
    heading.add_row(Text.assemble(('PGN 68','bold cyan'),('  /  '+title,'bold white')),
                    Text(status,style='bold '+COLORS.get(status,'cyan')))
    foot,foot_height,buttons,help_text=_footer(footer,width,height)
    parts=[Layout(Panel(heading,box=box.ROUNDED,border_style='cyan',padding=(0,1)),size=3),Layout(body,ratio=1)]
    if note is not None and not (isinstance(note,str) and not note):
        renderable=Text(str(note),style='yellow',no_wrap=False) if isinstance(note,str) else note
        from rich.align import Align
        note_rows=min(max(1,note_height),max(1,height-foot_height-5))
        parts.append(Layout(Align(renderable,vertical='bottom',height=note_rows),size=note_rows))
    if help_text:
        parts.append(Layout(Text(help_text,style='grey70',no_wrap=True,overflow='ellipsis'),size=1))
    parts.append(Layout(foot,size=foot_height))
    layout=Layout();layout.split_column(*parts)
    regions=list(context.pop('_view_hit_regions',[]))
    # Body controls may not extend into the anchored notes/footer after resize.
    body_bottom=height-foot_height-(1 if help_text else 0)
    if note is not None and not (isinstance(note,str) and not note):body_bottom-=note_rows
    regions=[dict(item,height=min(item['height'],body_bottom-item['y'])) for item in regions
             if item['y']<body_bottom and item.get('height',0)>0]
    layout.pgn_viewport=(width,height)
    layout.pgn_hit_regions=regions+buttons
    return layout


def render_main(context):
    width,height=_size(context)
    focus=max(0,min(2,int(context.setdefault('_ui_state',{}).get('main_focus',0))))
    choices=[('1','Search ranges','Choose a range, change settings and prepare adjacent searches.'),
             ('2','My sessions','Review saved searches, resume a session or open its results.'),
              ('3','Developer diagnostics','Record machine information to share with the developer.')]
    compact=height<27
    nav=Table.grid(expand=True,padding=(0,1));nav.add_column(width=3);nav.add_column(ratio=1)
    for i,(key,label,hint) in enumerate(choices):
        hovered=_hovered(key,'main',i)
        style='on '+('#1c465e' if hovered else BG) if hovered or i==focus else ''
        nav.add_row(Text('›'+key if i==focus else key,style='bold cyan'),Text(label,style='bold white'),style=style)
        nav.add_row('',Text(hint,style='grey78',no_wrap=True,overflow='ellipsis'),style=style)
        if not compact and i<len(choices)-1:nav.add_row('','')
    options=Panel(nav,title='Menu',title_align='left',border_style='cyan',box=box.ROUNDED,padding=(0 if compact else 1,1))
    body=Group(_progress(context,width),Text(''),options)
    regions=_body_text_regions(body,width,[(label,key,i,2)for i,(key,label,hint)in enumerate(choices)],'main')
    # Select the complete row including its descriptive line.
    for region in regions:region.update(x=2,width=max(1,width-4))
    regions.insert(0,dict(x=1,y=3,width=width-2,height=max(1,height-7),key='IGNORE',target='main',scrollable=True))
    context['_view_hit_regions']=regions
    from pgn_start_failures import start_failure_note
    return page('Main',body,context,'↑↓ Select · Enter Open · 1/2/3 Open',note=start_failure_note(context),note_height=4)


def render_workspace(context,workspace,selected,offset,message=None):
    context=dict(context,workspace=workspace)
    from pgn_workspace import range_cards
    from pgn_ui_workflow import category,primary,pause_control
    cards=range_cards(workspace);width,height=_size(context);count=max(1,(height-11)//3)
    item=cards[selected]if cards and selected<len(cards)else None
    counts={name:sum(category(c)==name for c in cards)for name in('Processing','Ready','Queued','Suspended')}
    heading=Text('   '.join(name+' '+str(number)for name,number in counts.items()),style='bold white')
    rows=[Panel(heading,title='Search ranges · 67–80 bits',title_align='left',border_style=MUTED,box=box.ROUNDED,padding=(0,1))]
    show_map=context.get('_ui_state',{}).get('workspace',{}).get('show_map',False)
    if show_map:rows.append(_range_overview(context,max(16,width-6)))
    start_y=3+3
    if show_map:
        from rich.console import Console
        map_height=len(Console(width=width).render_lines(rows[-1],Console(width=width).options,pad=False))
        start_y+=map_height;count=max(1,(height-11-map_height)//3)
    visible=cards[offset:offset+count]
    if visible:rows.extend(_card(c,offset+i==selected,offset+i)for i,c in enumerate(visible))
    else:rows.append(Panel(Text('Create a range with New. Saved plans appear here before any worker starts.',style='cyan'),box=box.ROUNDED))
    action=primary(item,context)
    footer=[dict(label=action['label'],shortcut='Enter',key='ACTIVATE',enabled=action['enabled']),
            dict(label='Edit',shortcut='E',key='e',enabled=bool(item and item.get('can_edit'))),
            dict(label='New',shortcut='N',key='n',enabled=True),
            dict(label='Remove',shortcut='Del',key='DELETE',enabled=bool(item and item.get('can_remove'))),
            dict(label='Launcher',shortcut='L',key='l',enabled=True),
            dict(label='Map',shortcut='M',key='m',enabled=True)]
    footer.insert(1,pause_control(context))
    from pgn_start_failures import start_failure_note
    ui=context.get('_ui_state',{})
    note=ui.get('request_error')or start_failure_note(context)or message or ui.get('request_notice')or 'Select a card, then use its primary action. Saved plans still require Native admission.'
    context['_view_hit_regions']=[dict(x=1,y=start_y+i*3,width=width-2,height=3,key='SELECT',target='workspace',index=offset+i)for i in range(len(visible))]
    context['_view_hit_regions'].insert(0,dict(x=1,y=start_y,width=width-2,height=max(1,height-9-start_y),key='IGNORE',target='workspace',scrollable=True))
    return page('Search ranges',Group(*rows),context,footer,note=note,note_height=2)

def _scroll_hint(offset, shown, total):
    total=max(0,int(total));offset=max(0,int(offset));last=min(total,offset+max(0,int(shown)))
    text=Text()
    if offset>0:text.append('↑  ',style='bold cyan')
    text.append(f'{offset+1 if total else 0}–{last} / {total}',style='grey70')
    if last<total:text.append('  ↓',style='bold cyan')
    return text


def _parameter_metrics(model,context):
    from rich.console import Console
    width,height=_size(context);side=width>=100
    kind=model.get('save_kind') or ('pending_edit' if model.get('queue_edit') else 'launcher' if model.get('basis')=='launcher' else 'draft')
    save={'draft':'Save range','launcher':'Save launcher','pending_edit':'Apply pending edit'}[kind]
    footer='Enter Edit · Ctrl+S '+save
    if kind=='draft':footer+=' · G Start · A Add · V Plans · T Advanced'
    elif kind=='launcher':footer+=' · T Advanced'
    if kind=='draft':footer+=' · L Launcher'
    validation=str(model.get('validation_error')or'');status=str(model.get('status_note')or'')
    notes=[Text(str(model.get('field_help')or''),style='grey70',no_wrap=True,overflow='ellipsis')]
    if kind=='launcher':notes.insert(0,Text('LOCAL LAUNCHER DEFAULTS — saved for the NEXT application launch; the current search is unchanged.',style='bold cyan',no_wrap=True,overflow='ellipsis'))
    if validation:notes.append(Text(validation,style='bold red',no_wrap=True,overflow='ellipsis'))
    if status and status!=validation:notes.append(Text(status,style='yellow',no_wrap=True,overflow='ellipsis'))
    preview=_parameter_preview(model)
    preview_height=0
    if not side:
        console=Console(width=width);preview_height=len(console.render_lines(preview,console.options,pad=False))
    footer_height=_footer(footer,width,height)[1]
    # Reserve the final scrolling-counter line as well as every actual note.
    capacity=max(1,height-3-footer_height-(len(notes)+1)-2-preview_height)
    shown=min(capacity,len(model.get('rows')or[]));note=_scroll_hint(model.get('offset',0),shown,model.get('total',shown))
    note.append(' · ←/→ options · Enter edit',style='grey58');notes.append(note)
    return dict(kind=kind,footer=footer,validation=validation,notes=notes,preview=preview,capacity=capacity)


def render_parameter_editor(model,context):
    from rich.style import Style
    width,height=_size(context);side=width>=100
    sidebar_width=33 if side else 0
    field_width=width-sidebar_width-1 if side else width
    value_width=max(12,field_width-32)
    table=Table.grid(expand=False,padding=(0,1));table.add_column(width=2);table.add_column(width=20);table.add_column(width=value_width)
    metrics=_parameter_metrics(model,context)
    rows=(model.get('rows') or [])[:metrics['capacity']];caret_offsets={};editing_index=None
    for relative,row in enumerate(rows):
        row=dict(row);row.setdefault('index',int(model.get('offset',0))+relative)
        index=int(row['index']);selected=bool(row.get('selected'));invalid=bool(row.get('invalid'))
        label=str(row.get('label',row.get('name',''))).replace('_',' ').title()
        if str(row.get('name'))=='gpu':label='GPU'
        label_text=Text(label,style='bold red' if invalid else 'bold white' if selected else 'white',no_wrap=True,overflow='ellipsis')
        label_text.stylize(Style(meta={'pgn_field_row':index}))
        if row.get('choices'):
            value=_parameter_choices(row,value_width)
        else:
            if row.get('can_pick_folder') and str(row.get('name','')).lower() in ('output','resume'):
                value,caret=_parameter_folder_value(row,value_width)
            else:
                value,caret=_parameter_value(row,value_width)
            if row.get('editing'):
                caret_offsets[index]=caret;editing_index=index
        indicator=Text('!' if invalid else '›' if selected else '',style='bold red' if invalid else 'bold cyan')
        table.add_row(indicator,label_text,value,style='on '+BG if selected else '')
    kind=metrics['kind']
    title='Launcher settings' if kind=='launcher' else 'Pending range' if kind=='pending_edit' else 'New search'
    fields=Panel(table,title=title,title_align='left',border_style='red' if model.get('validation_errors') else 'cyan',box=box.ROUNDED,padding=(0,1),height=metrics['capacity']+2)
    preview=metrics['preview']
    if side:
        body=Layout();body.split_row(Layout(fields,size=field_width),Layout(Text(' '),size=1),Layout(preview,size=sidebar_width))
    else:
        body=Group(fields,preview)
    footer=metrics['footer'];validation=metrics['validation'];note_lines=metrics['notes']
    raw_specs,_=_footer_specs(footer)
    pending=bool(context.get('_ui_state',{}).get('pending_worker_request'))
    invalid=bool(validation or model.get('validation_errors'))
    from pgn_ui_workflow import phase
    footer=[]
    for label,shortcut,key in raw_specs:
        enabled=not invalid if key=='SAVE'else True
        if key in ('g','a'):
            enabled=not(invalid or pending)
            if key=='g'and phase(context)in('STARTING','SEARCHING'):label='Switch now'
        footer.append(dict(label=label,shortcut=shortcut,key=key,enabled=enabled))

    context['_view_hit_regions']=[]
    page_title='Launcher defaults (next launch)' if kind=='launcher' else 'Search parameters'
    result=page(page_title,body,context,footer,note=Group(*note_lines),note_height=len(note_lines))
    result.pgn_parameter_capacity=metrics['capacity']
    _parameter_geometry(result,width,height,field_width,caret_offsets,editing_index)
    return result

def render_arrow_list(title,entries,selected,offset,total,context,footer):
    width,height=_size(context)
    sessions=str(title).strip().lower()=='my sessions'
    table=Table.grid(expand=True,padding=(0,1));table.add_column(width=2);table.add_column(ratio=1)
    if sessions:table.add_column(width=18,no_wrap=True)
    for i,entry in enumerate(entries):
        absolute=offset+i;chosen=absolute==selected
        label=Text(str(entry.get('label','')),style='bold white'if chosen else'white',no_wrap=True,overflow='ellipsis')
        detail=Text(str(entry.get('detail','')),style='grey78'if chosen else MUTED,no_wrap=True,overflow='ellipsis')
        cells=['›'if chosen else'',Group(label,detail)]
        if sessions:cells.append(_button('Open results','R','r','list',absolute))
        table.add_row(*cells,style='on '+BG if chosen else'')
    if not entries:
        table.add_row(*(['','No saved sessions']+(['']if sessions else[])))
    body=Panel(table,border_style=MUTED,box=box.ROUNDED,padding=(0,1))
    note=_scroll_hint(offset,len(entries),total)
    regions=[dict(x=2,y=4+i*2,width=width-4,height=2,key='ENTER',target='list',index=offset+i)for i in range(len(entries))]
    regions.insert(0,dict(x=1,y=4,width=width-2,height=max(1,height-10),key='IGNORE',target='list',scrollable=True))
    if sessions:
        # This exact label is projected once for each actual session row. The
        # cell offset follows Rich's table sizing, including wide Unicode text.
        from rich.console import Console
        from rich.cells import cell_len
        console=Console(width=width)
        lines=console.render_lines(body,console.options,pad=False)
        row=0;needle=' Open results [R] '
        for y,segments in enumerate(lines):
            line=''.join(segment.text for segment in segments);x=line.find(needle)
            if x>=0 and row<len(entries):
                regions.append(dict(x=cell_len(line[:x]),y=3+y,width=cell_len(needle),height=1,
                                    key='r',target='list',index=offset+row));row+=1
        footer=' · '.join(part for part in str(footer).split(' · ')
                          if not part.strip().startswith('R '))
    context['_view_hit_regions']=regions
    return page(title,body,context,footer,note=note)


def render_report(lines,selected,offset,total,context):
    return page('Saved results',Panel(Text('\n'.join(lines),no_wrap=True,overflow='ellipsis'),border_style=MUTED,box=box.ROUNDED,padding=(0,1)),context,
                '↑↓ Scroll · R Open results',note=_scroll_hint(offset,len(lines),total))


def _parameter_value(row,width):
    from rich.cells import cell_len
    from rich.style import Style
    index=int(row['index']);editing=bool(row.get('editing'))
    color='bold red' if row.get('invalid') else 'bold cyan' if editing else MUTED if row.get('readonly') else 'white'
    caret=None
    if editing:
        value=str(row.get('edit_buffer') if row.get('edit_buffer') is not None else row.get('value',''))
        cursor=max(0,min(len(value),int(row.get('cursor') or 0)))
        interior=max(1,width-2);left=0
        while left<cursor and cell_len(value[left:cursor])>=interior:left+=1
        right=left;used=0
        while right<len(value) and used+cell_len(value[right])<=interior:
            used+=cell_len(value[right]);right+=1
        visible=Text(value[left:right],style=color)
        if row.get('selected_all'):visible.stylize('reverse')
        text=Text('‹' if left else ' ',style='grey58');text.append_text(visible)
        text.append(' '*(interior-used),style=color)
        text.append('›' if right<len(value) else ' ',style='grey58')
        caret=1+cell_len(value[left:cursor])
    else:
        text=Text(str(row.get('value','')) or '—',style=color,no_wrap=True)
        text.truncate(width,overflow='ellipsis',pad=True)
    text.stylize(Style(meta={'pgn_field_value':index}))
    return text,caret

def _parameter_choices(row,width):
    from rich.style import Style
    index=int(row['index']);line=Text()
    for choice in row.get('choices') or ():
        if line:line.append(' ')
        key=str(choice['key']);active=bool(choice.get('active'))
        hovered=_hovered(key,'parameters',index)
        color='bright_green' if active else 'white'
        background='#285c3b' if active and hovered else '#173f29' if active else '#24506c' if hovered else '#182d3a'
        style=Style(color=color,bgcolor=background,bold=active,
                    meta={'pgn_field_value':index,'pgn_choice':key,'pgn_choice_index':index})
        line.append(' '+str(choice.get('label',choice.get('value','')))+' ',style)
    # The short supported enum sets fit the value column; never ellipsize a
    # clickable option into an ambiguous or invisible target.
    return line

def _parameter_preview(model):
    if model.get('basis')=='launcher' or model.get('save_kind')=='launcher':
        from pathlib import Path
        filename=Path(str(model.get('launcher_path') or 'No launcher selected')).name
        body=Group(Text('LOCAL LAUNCHER FILE',style='bold cyan'),Text(filename,style='bold white',no_wrap=True,overflow='ellipsis'),Text(str(model.get('launcher_path') or 'No launcher selected'),overflow='fold'),Text(''),Text('Defaults for NEXT launch only.',style='yellow'),Text('Ctrl+S: Save launcher\nEsc / Back: return\nNo Start / Add / range save here.',style='white'))
        return Panel(body,title='Launcher purpose & path',title_align='left',border_style='cyan',box=box.ROUNDED,padding=(0,1))
    preview=model.get('range_preview');eta=model.get('eta')or{};rows=[]
    if preview:
        for label,key in (('Start','start'),('End','end'),('Total positions','positions')):
            rows.append(Text(label,style='grey70'))
            rows.append(Text(sci(preview[key]),style='bold white',no_wrap=True,overflow='ellipsis'))
    else:rows.append(Text('Enter a valid start and length or end.',style='red'))
    threshold=model.get('threshold_preview')
    if threshold:
        rows.extend((Text('Threshold request',style='grey70'),Text(threshold['summary'],style='bold cyan'),Text(threshold['actual_label'],style='yellow',overflow='fold')))
    return Panel(Group(*rows),title='Range preview',title_align='left',border_style=MUTED,box=box.ROUNDED,padding=(0,1))

def _parameter_geometry(layout,width,height,field_width,caret_offsets,editing_index):
    from rich.cells import cell_len
    from rich.console import Console
    console=Console(width=width,height=height,legacy_windows=False)
    lines=console.render_lines(layout,console.options,pad=True)
    row_positions={};values={};choices={}
    for y,line in enumerate(lines):
        x=0
        for segment in line:
            count=cell_len(segment.text);meta=segment.style.meta if segment.style else {}
            if 'pgn_field_row' in meta:row_positions.setdefault(int(meta['pgn_field_row']),y)
            if 'pgn_field_value' in meta:values.setdefault(int(meta['pgn_field_value']),(x,y))
            if 'pgn_choice' in meta:
                identity=(str(meta['pgn_choice']),int(meta['pgn_choice_index']))
                if identity in choices:choices[identity]['width']+=count
                else:choices[identity]=dict(x=x,y=y,width=count,height=1,key=identity[0],target='parameters',index=identity[1])
            x+=count
    regions=[r for r in getattr(layout,'pgn_hit_regions',())if r.get('target')=='footer']
    if row_positions:
        top=min(row_positions.values());bottom=max(row_positions.values())+1
        regions.insert(0,dict(x=1,y=top,width=max(1,field_width-2),height=bottom-top,key='IGNORE',target='parameters',scrollable=True))
    regions.extend(dict(x=2,y=y,width=max(1,field_width-4),height=1,key='ENTER',target='parameters',index=index)
                   for index,y in row_positions.items())
    regions.extend(choices.values())
    layout.pgn_hit_regions=regions
    layout.pgn_caret={'visible':False}
    if editing_index in values and caret_offsets.get(editing_index) is not None:
        x,y=values[editing_index];x+=caret_offsets[editing_index]
        if 0<=x<width and 0<=y<height:
            layout.pgn_caret=dict(x=x,y=y,visible=True,blink=True)

def _parameter_disable_save(layout):
    for region in getattr(layout,'pgn_hit_regions',()):
        if region.get('target')=='footer' and region.get('key')=='SAVE':region['disabled']=True
    try:
        panel=layout.children[-1].renderable
        for text in panel.renderable.renderables:
            if not isinstance(text,Text):continue
            for region in layout.pgn_hit_regions:
                if region.get('disabled') and region.get('painted'):
                    start=text.plain.find(region['painted'])
                    if start>=0:text.stylize('grey50 on grey15',start,start+len(region['painted']))
    except (AttributeError,IndexError):
        pass


def _parameter_folder_value(row,width):
    """Reserve the chooser cells before horizontal scrolling the editable path."""
    from rich.cells import cell_len
    from rich.style import Style
    index=int(row['index']);key=str(row.get('browse_key') or 'PICK_FOLDER')
    label=' Select folder [B] '
    path_width=max(3,width-cell_len(label)-1)
    path,caret=_parameter_value(row,path_width)
    path.append(' ')
    background='#276b91' if _hovered(key,'parameters',index) else '#16415b'
    path.append(label,Style(color='bright_cyan',bgcolor=background,bold=True,
        meta={'pgn_choice':key,'pgn_choice_index':index}))
    return path,caret
