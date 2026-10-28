"""Synthetic fixtures only: no assertion of publication provenance."""
import pytest
from scripts.science import source_context_0193 as v
from scripts.science.obelix_solo_oxide_five_doi_0188 import S18, T18
from scripts.science.obelix_solo_oxide_process_transfer_0191 import S20
from scripts.science.obelix_solo_oxide_jats_three_doi_0187 import COND2020


def source_2018():
    head = ('<article><front><article-meta><article-id pub-id-type="doi">10.1039/c8ra01329b</article-id>'
            '<article-id pub-id-type="pmc">9079727</article-id></article-meta></front>'
            '<body><p>Li6.4Al0.2La3Zr2O12 impedance conductivity was measured at 25 °C (298 K).</p></body>'
            '<floats-group><table-wrap><caption><p>Sample denotation and sintering conditions</p></caption>'
            '<table><tr><th>Sample</th><th>Sintering</th></tr>')
    from scripts.science.obelix_solo_oxide_process_transfer_0191 import S18 as conditions
    head += ''.join(f'<tr><td>{name}</td><td>{temp} C x {minutes//60} h</td></tr>' for name,temp,minutes in conditions)
    head += ('</table></table-wrap><table-wrap><caption><p>Other</p></caption><table><tr><td>x</td></tr>'
             '</table></table-wrap><table-wrap><caption><p>Summary of ionic conductivity data</p></caption>'
             '<table><tr><th>Sample</th><th>total conductivity (S/cm)</th><th>bulk conductivity (S/cm)</th></tr>')
    head += ''.join(f'<tr><td>{name}</td><td>{value:.2e}</td><td>1e-3</td></tr>' for name,value in zip(S18,T18))
    return (head+'</table></table-wrap></floats-group></article>').encode()


def source_2020():
    table=('<table-wrap><label>Table 2.</label><caption><p>Total ionic conductivity at 25 C</p></caption>'
           '<table><tr><th>Sample</th><th>Sintering Condition</th>'
           '<th>Total ionic conductivity (10-4 S cm-1)</th><th>Bulk conductivity</th></tr>')
    table += ''.join(f'<tr><td>{name}</td><td>{temp} C x {minutes} min</td><td>{value}</td><td>99</td></tr>'
                     for (name,temp,minutes),value in zip(S20,COND2020))
    return (f'<article><front><article-meta><article-id pub-id-type="doi">{v.DOIS[2]}</article-id>'
            '<article-id pub-id-type="pmc">7040616</article-id></article-meta></front>'
            '<body><p>Li6.6La3Zr1.6Nb0.4O12 LLZO conductivity.</p></body><floats-group>'
            +table+'</table></table-wrap></floats-group></article>').encode()


def test_2018_binds_rows_without_claiming_authentication():
    result=v.inspect_jats(source_2018(),v.DOI18)
    assert result['source_authentication']=='NOT_PERFORMED' and not result['admitted']
    assert result['measurement_temperature_context']=='KELVIN_298K_PAIRED_WITH_25C_TEXT'
    assert [(r['sintering_temperature_C'],r['dwell_min']) for r in result['rows'][3:]]==[(1210,900),(1220,600)]
    assert result['rows'][3]['total_conductivity_S_cm']==pytest.approx(2.10e-4)


def test_2018_table_kelvin_headers_are_linked_to_25c_prose():
    source=source_2018().replace(
        'impedance conductivity was measured at 25 °C (298 K).'.encode(),
        'ionic conductivity at 25 °C is listed in Table 3.'.encode())
    source=source.replace(b'total conductivity (S/cm)',b'total conductivity 298 K (S/cm)')
    source=source.replace(b'bulk conductivity (S/cm)',b'bulk conductivity 298 K (S/cm)')
    source=source.replace(b'</body>',b'<p>LLZAO-4 is a prose label.</p></body>')
    result=v.inspect_jats(source,v.DOI18)
    assert result['measurement_temperature_context']=='KELVIN_298K_PAIRED_WITH_25C_TEXT'
    assert result['rows'][3]['sample']=='LLZALO-4'
    assert not result['admitted'] and result['source_authentication']=='NOT_PERFORMED'
    with pytest.raises(ValueError, match='unpaired'):
        v.inspect_jats(source.replace(b'bulk conductivity 298 K',b'bulk conductivity 300 K'),v.DOI18)
    with pytest.raises(ValueError):
        v.inspect_jats(source.replace(b'listed in Table 3',b'listed elsewhere'),v.DOI18)


def test_2020_binds_sample_and_total_column():
    result=v.inspect_jats(source_2020(),v.DOIS[2])
    assert result['measurement_temperature_context']=='EXACT_25C_STATED'
    assert [(r['sintering_temperature_C'],r['dwell_min']) for r in result['rows'][:2]]==[(1200,60),(1200,30)]
    assert result['rows'][1]['total_conductivity_S_cm']==pytest.approx(5.09e-4)
    assert result['scientific_verdict']=='INCONCLUSIVE' and not result['scientific_GO']

def test_nominal_room_temperature_source_is_not_upgraded():
    with pytest.raises(ValueError, match='unsupported DOI'):
        v.inspect_jats(source_2020(), '10.1021/acsomega.2c06544')


@pytest.mark.parametrize('mutation', [
    lambda b:b.replace(b'10.1039/c8ra01329b',b'10.1039/forged'),
    lambda b:b.replace('25 °C (298 K)'.encode(),b'1250 C, citation 25'),
    lambda b:b.replace('25 °C (298 K)'.encode(),b'25 C and 30 C'),
    lambda b:b.replace(b'impedance conductivity was measured',b'impedance conductivity sample prepared'),
    lambda b:b.replace(b'1210 C x 15 h',b'1220 C x 15 h'),
    lambda b:b.replace(b'2.10e-04',b'1.32e-04'),
    lambda b:b.replace(b'total conductivity (S/cm)',b'total conductivity (mS/cm)'),
])
def test_2018_rejects_identity_context_and_table_mutations(mutation):
    with pytest.raises(ValueError):v.inspect_jats(mutation(source_2018()),v.DOI18)


@pytest.mark.parametrize('mutation', [
    lambda b:b.replace(b'25 C</p></caption>',b'25 K</p></caption>'),
    lambda b:b.replace(b'<td>5.09</td><td>99</td>',b'<td>99</td><td>5.09</td>'),
    lambda b:b.replace(b'1200 C x 30 min',b'1200 C x 60 min'),
    lambda b:b.replace(b'10-4 S cm-1',b'10-4 mS cm-1'),
    lambda b:b.replace(b'<td>SL2</td>',b'<td>SL1</td>'),
])
def test_2020_rejects_temperature_column_and_sample_mutations(mutation):
    with pytest.raises(ValueError):v.inspect_jats(mutation(source_2020()),v.DOIS[2])
