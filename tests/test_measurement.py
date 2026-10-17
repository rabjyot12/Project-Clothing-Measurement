from app.measurement import calculate,mae

def test_known_distance():
    r=calculate(((0,0),(150,0)),15,{'waist_width':((0,0),(400,0))})
    assert r['measurements_cm']['waist_width']==40

def test_horizontal_vertical_same_scale():
    r=calculate(((0,0),(0,150)),15,{'x':((0,0),(100,0)),'y':((0,0),(0,100))})
    assert r['measurements_cm']['x']==r['measurements_cm']['y']==10

def test_validation():
    assert mae({'x':10.7,'y':20.2},{'x':10,'y':20})['target_met']
    assert not mae({'x':13},{'x':10})['target_met']
