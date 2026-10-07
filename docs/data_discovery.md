# Data discovery IBGE/SIDRA

Gerado em: 2026-10-07T20:22:59

## Documentação oficial consultada

- API de dados agregados do IBGE/SIDRA: https://servicodados.ibge.gov.br/api/docs/agregados?versao=3
- API de localidades do IBGE: https://servicodados.ibge.gov.br/api/docs/localidades
- Lista de municípios usada como referência: https://servicodados.ibge.gov.br/api/v1/localidades/municipios

## Fontes testadas

### population_estimate

- Tabela SIDRA: `6579`
- Endpoint dados: `https://apisidra.ibge.gov.br/values/t/6579/n6/all/v/9324/p/2024/h/y/f/a/d/m`
- Período consultado: `2024`
- Variáveis: 9324
- Linhas Bronze: 5571
- Linhas Silver: 5571
- Municípios distintos: 5571
- Colunas Bronze: nc, nn, mc, mn, v, d1c, d1n, d2c, d2n, d3c, d3n

### municipal_gdp

- Tabela SIDRA: `5938`
- Endpoint dados: `https://apisidra.ibge.gov.br/values/t/5938/n6/all/v/37/p/2021/h/y/f/a/d/m`
- Período consultado: `2021`
- Variáveis: 37
- Linhas Bronze: 5570
- Linhas Silver: 5570
- Municípios distintos: 5570
- Colunas Bronze: nc, nn, mc, mn, v, d1c, d1n, d2c, d2n, d3c, d3n

### cempre_general

- Tabela SIDRA: `9509`
- Endpoint dados: `https://apisidra.ibge.gov.br/values/t/9509/n6/all/v/706,367,707,708,662,10143/p/2024/h/y/f/a/d/m`
- Período consultado: `2024`
- Variáveis: 706, 367, 707, 708, 662, 10143
- Linhas Bronze: 33420
- Linhas Silver: 33420
- Municípios distintos: 5570
- Colunas Bronze: nc, nn, mc, mn, v, d1c, d1n, d2c, d2n, d3c, d3n

### census_area_density

- Tabela SIDRA: `4714`
- Endpoint dados: `https://apisidra.ibge.gov.br/values/t/4714/n6/all/v/93,6318,614/p/2022/h/y/f/a/d/m`
- Período consultado: `2022`
- Variáveis: 93, 6318, 614
- Linhas Bronze: 16710
- Linhas Silver: 16710
- Municípios distintos: 5570
- Colunas Bronze: nc, nn, mc, mn, v, d1c, d1n, d2c, d2n, d3c, d3n

## Tabela Gold inicial

- Linhas: 5571
- Colunas: 19
- Municípios distintos: 5571
- Colunas: municipality_code, municipality_name_ref, state_code, state, state_name, region, population_estimated, gdp_current_brl_thousand, active_companies, avg_monthly_salary_brl, employed_salaried, employed_total, local_units, wages_brl_thousand, area_km2, census_population, density_per_km2, gdp_per_capita_estimated, active_companies_per_1000_inhabitants
- Valores nulos por coluna: {'population_estimated': 1, 'gdp_current_brl_thousand': 1, 'active_companies': 1, 'avg_monthly_salary_brl': 1, 'employed_salaried': 1, 'employed_total': 1, 'local_units': 1, 'wages_brl_thousand': 1, 'area_km2': 1, 'census_population': 1, 'density_per_km2': 1, 'gdp_per_capita_estimated': 1, 'active_companies_per_1000_inhabitants': 1}
- Problemas de validação: nenhum problema crítico encontrado

Observação territorial: a base de localidades do IBGE já traz `Boa Esperança do Norte` (`5101837`), em Mato Grosso. Nas consultas SIDRA testadas, esse município aparece sem valor (`...`) ou ainda não aparece em PIB/Censo/CEMPRE, o que reforça a necessidade de controlar safra territorial e período de cada fonte.

## Viabilidade do projeto

**SIM, COM RESSALVAS.** A PoC conseguiu conectar em APIs oficiais do IBGE, obter dados municipais, integrar mais de uma fonte pelo código municipal e gerar uma primeira Gold com uma linha por município. As ressalvas principais são escolher variáveis com granularidade municipal, documentar diferenças de período entre fontes e evitar consultas muito amplas de tabelas com classificações detalhadas, como CEMPRE por CNAE.

## Próximos passos recomendados

- Manter População/Área/Densidade, PIB dos Municípios e CEMPRE geral como fontes iniciais.
- Investigar variáveis de idade, renda e escolaridade do Censo 2022 antes do clustering.
- Usar CEMPRE por CNAE em amostras controladas para criar indicadores setoriais derivados, não como extração bruta total no primeiro momento.
- Criar indicadores derivados: PIB per capita, empresas por 1.000 habitantes, empregos por 1.000 habitantes, salário médio, densidade e composição econômica.
