"""Incremental committed-prefix projection; no full-history scan per frame.

Normal progress touches only the changed lower-prime interval. Rollback clears
only that interval, subtracts its bins, and refills bounded rank/recent caches
through visible/threshold indexes. Disk grows with records; RAM does not.
"""
import copy


def encoded(number):return int(number).to_bytes(16,'big')
def decoded(value):return int.from_bytes(value,'big')


class Projection:
    def __init__(self,index,configuration,rebuild=False):
        self.index=index;self.db=index.db
        self.start=int(configuration['start'])
        self.count=int(configuration.get('count_gap',configuration.get('min_gap',960)))
        self.detail=int(configuration.get('detail_gap',configuration.get('min_gap',960)))
        self.limit=max(30,int(configuration.get('report_top',100)))
        first=((self.count+99)//100)*100
        self.thresholds=sorted({self.count,*[value for value in range(first,first+600,100) if value>self.count]})
        self.value=None if rebuild else index.meta('projection')
        if self.value is None or 'threshold_counts' not in self.value:
            progress=index.meta('progress',{})
            prefix=self.start+int(progress.get('positions',0))
            self.db.execute('UPDATE gaps SET visible=(lo<?),count_ok=(gap>=?),detail_ok=(gap>=?)',
                            (encoded(prefix),self.count,self.detail))
            value={'prefix':str(prefix),'counts':[0]*(len(index.bounds)-1),'count_total':0,'detail_total':0,'threshold_counts':{str(t):0 for t in self.thresholds}}
            for group,count in self.db.execute('SELECT bin,COUNT(*) FROM gaps WHERE visible=1 AND count_ok=1 GROUP BY bin'):
                value['counts'][group]=count;value['count_total']+=count
            value['detail_total']=self.db.execute('SELECT COUNT(*) FROM gaps WHERE visible=1 AND detail_ok=1').fetchone()[0]
            for threshold in self.thresholds:
                value['threshold_counts'][str(threshold)]=self.db.execute('SELECT COUNT(*) FROM gaps WHERE visible=1 AND gap>=?',(threshold,)).fetchone()[0]
            self.refill(value);index.put_meta('projection',value);self.db.commit();self.value=value

        if set(self.value.get('threshold_counts',{}))!={str(t)for t in self.thresholds}:
            self.value=copy.deepcopy(self.value)
            self.value['threshold_counts']={str(t):self.db.execute('SELECT COUNT(*) FROM gaps WHERE visible=1 AND gap>=?',(t,)).fetchone()[0]for t in self.thresholds}
        if self.value.get('view_cache_version')!=3:
            value=copy.deepcopy(self.value);self.refill(value);index.put_meta('projection',value);self.db.commit();self.value=value

    def refill(self,value):
        value['view_cache_version']=3
        for name,column in (('count','count_ok'),('detail','detail_ok')):
            value[name+'_top']=[[int(gap),str(decoded(lo)),int(seq)] for gap,lo,seq in self.db.execute(
                'SELECT gap,lo,seq FROM gaps WHERE visible=1 AND '+column+'=1 ORDER BY gap DESC,lo LIMIT ?',
                (self.limit,))]
        value['recent']=[[int(gap),str(decoded(lo)),int(seq)] for gap,lo,seq in self.db.execute(
            'SELECT gap,lo,seq FROM gaps WHERE visible=1 AND count_ok=1 ORDER BY seq DESC LIMIT 30')]

    def inserted(self,low,high,group,sequence):
        if low>=int(self.value['prefix']):return self.value
        value=copy.deepcopy(self.value);gap=high-low
        if gap>=self.count:value['counts'][group]+=1;value['count_total']+=1
        if gap>=self.detail:value['detail_total']+=1
        for threshold in self.thresholds:
            if gap>=threshold:value['threshold_counts'][str(threshold)]+=1
        self.refill(value)
        return value

    def move(self,prefix):
        old=int(self.value['prefix'])
        if prefix==old:return self.value
        value=dict(self.value);value['prefix']=str(prefix)
        left,right=sorted((old,prefix));delta=1 if prefix>old else -1
        cursor=self.db.execute('SELECT gap,bin FROM gaps WHERE lo>=? AND lo<?',(encoded(left),encoded(right)))
        first=cursor.fetchone()
        if first is None:
            # No new/removed qualifying row: update only the scalar frontier.
            return value
        value=copy.deepcopy(value)
        def accept(row):
            gap,group=row
            if gap>=self.count:value['counts'][group]+=delta;value['count_total']+=delta
            if gap>=self.detail:value['detail_total']+=delta
            for threshold in self.thresholds:
                if gap>=threshold:value['threshold_counts'][str(threshold)]+=delta
        accept(first)
        for row in cursor:accept(row)
        self.db.execute('UPDATE gaps SET visible=? WHERE lo>=? AND lo<?',
                        (1 if delta>0 else 0,encoded(left),encoded(right)))
        self.refill(value)
        return value
