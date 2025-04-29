import csv
import json

def converter_csv_para_json(csv_filepath, json_filepath):
    """Converte um arquivo CSV para JSON."""
    data = []
    with open(csv_filepath, mode='r', encoding='utf-8') as csvfile:
        csv_reader = csv.DictReader(csvfile)
        for row in csv_reader:
            # Limpar espaços em branco dos valores e converter vírgula para ponto em números
            cleaned_row = {}
            for key, value in row.items():
                cleaned_value = value.strip()
                if cleaned_value.replace(',', '').isdigit() and ',' in cleaned_value:
                    cleaned_value = cleaned_value.replace(',', '.')
                cleaned_row[key.strip()] = cleaned_value
            data.append(cleaned_row)

    with open(json_filepath, mode='w', encoding='utf-8') as jsonfile:
        json.dump(data, jsonfile, indent=4)

if __name__ == "__main__":
    csv_arquivo = 'dados_candidatos.csv'
    json_arquivo = 'dados_candidatos.json'
    converter_csv_para_json(csv_arquivo, json_arquivo)
    print(f"Arquivo '{csv_arquivo}' convertido para '{json_arquivo}' com sucesso!")