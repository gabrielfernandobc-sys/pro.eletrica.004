with open('index.html', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

targets = [
    'abrirModalConfigParedes',
    'fecharModalConfigParedes',
    'selecionarPresetEspessura',
    'salvarConfigParedes',
    'aplicarDimensoesComodo',
    'atualizarPreviewEspessuraComodo',
    'btnConfigParedesCad'
]

for i, line in enumerate(lines):
    for t in targets:
        if t in line:
            print(f"{t} -> line {i+1}: {line.strip()[:90]}")


