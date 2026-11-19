import pytest
from core.exceptions import ReportError
from sources.task_files import task_rows, TaskFilesReader


def test_task_csv_to_snapshot(tmp_path):
    path=tmp_path/'tasks.csv'
    path.write_text('userId,id,title,completed\n1,1,First,true\n1,2,Second,false\n')
    snapshot=TaskFilesReader([path]).read().snapshot
    assert snapshot.mode=='uploaded_files'
    assert len(snapshot.tasks)==2 and snapshot.tasks[0].completed
    assert not snapshot.tasks[1].completed


@pytest.mark.parametrize('row', [[1,1,'Task','yes'],[1,'bad','Task','true'],[1,1,'','true']])
def test_invalid_task_values(row):
    with pytest.raises(ReportError):
        task_rows([['userId','id','title','completed'],row])


def test_duplicate_tasks_across_files(tmp_path):
    path=tmp_path/'tasks.csv'
    path.write_text('userId,id,title,completed\n1,1,Task,true\n')
    with pytest.raises(ReportError,match='Duplicate task'):
        TaskFilesReader([path,path]).read()


def test_new_task_attributes():
    tasks=task_rows([['Task ID','Task Name','User ID','Status','Created'],[101,'Check backups',2,'Completed','2026/10/3']])
    assert tasks[0].completed and str(tasks[0].created)=='2026-10-03'


@pytest.mark.parametrize('status,created',[('Unknown','2026-10-03'),('Pending','2026-02-30'),('Completed','')])
def test_new_task_attribute_validation(status,created):
    with pytest.raises(ReportError):
        task_rows([['Task ID','Task Name','User ID','Status','Created'],[101,'Check backups',2,status,created]])
