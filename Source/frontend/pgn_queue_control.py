"""Queue plans are durable preparation, NOT Native admission.
Only actual Start/Resume queries the Native image/threshold plan.
"""
from pgn_queue import enqueue_next,pending_ranges,update_pending,remove_pending
def apply_queue_request(store,action,gpu_index,check_end=None,gpu_uuid_for_index=None):
    values=dict(action.values);kind=action.kind;identifier=values.pop('child_session_id',None)
    if kind=='queue_delete':return remove_pending(store,identifier,reflow_following=values.get('reflow_following')is True)
    if kind not in ('queue','queue_edit'):raise ValueError('Unsupported queue action')
    selected=int(values.get('gpu',gpu_index))
    gpu_uuid=gpu_uuid_for_index(selected)if gpu_uuid_for_index else None
    # _configuration validates exact scope/raw policy before the queue WAL publishes.
    # Driver memory/echo binding stays PENDING and is mandatory in the engine.
    if kind=='queue_edit':return update_pending(store,identifier,values,gpu_index,gpu_uuid=gpu_uuid)
    return enqueue_next(store,values,gpu_index,gpu_uuid=gpu_uuid)
