import subprocess
import pytest
from rhombus.automation.ledger import canonical, INITIAL_LEDGER
from scripts.tools.validate_kaggle_bootstrap import inspect_root


def test_inspector_recognizes_only_exact_parentless_root(tmp_path):
    def git(*args,input=None):
        return subprocess.check_output(['git','-C',str(tmp_path),*args],input=input).decode().strip()
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    blob=git('hash-object','-w','--stdin',input=canonical(INITIAL_LEDGER))
    tree=git('mktree',input=f'100644 blob {blob}\tstate.json\n'.encode())
    args=['-c','user.name=offline','-c','user.email=offline@example.invalid','commit-tree',tree,'-m','root']
    root=git(*args)
    report=inspect_root(tmp_path,root)
    assert report['structure']=='PASS_OFFLINE' and report['submission_authorization'] is False
    assert report['owner_approval']=='UNVERIFIED' and report['production_readiness']=='NO_GO'
    child=git('-c','user.name=offline','-c','user.email=offline@example.invalid','commit-tree',tree,'-p',root,'-m','child')
    with pytest.raises(ValueError,match='parentless'):inspect_root(tmp_path,child)
    with pytest.raises(ValueError):inspect_root(tmp_path,'HEAD')


def test_deployment_inventory_binds_retained_science():
    from scripts.tools.kaggle_deployment_inventory import inventory
    result=inventory()
    assert len(result['source_files']) == 283
    assert len(result['parent_artifacts']) == 20
    assert result['source_commit']=='474df8faa7484b87f19e5679336192939598e1f7'
    assert result['production_readiness']=='NO_GO'
