from django.core.management.base import BaseCommand
from django.core import serializers
from django.db import transaction
from books.models import Language, Author, Book, Chapter, BookFile, ChangeLog
import json
import os

class Command(BaseCommand):
    help = 'Export books app data to fixtures'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='webnovel/fixtures',
            help='Output directory for fixtures'
        )
        parser.add_argument(
            '--models',
            nargs='+',
            choices=['Language', 'Author', 'Book', 'Chapter', 'BookFile', 'ChangeLog'],
            help='Specific models to export'
        )
        parser.add_argument(
            '--natural-foreign',
            action='store_true',
            help='Use natural foreign keys'
        )
        parser.add_argument(
            '--exclude-files',
            action='store_true',
            help='Exclude file fields from export'
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        models_to_export = options['models'] or ['Language', 'Author', 'Book', 'Chapter', 'BookFile', 'ChangeLog']
        use_natural = options['natural_foreign']
        exclude_files = options['exclude_files']

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Model mapping
        model_map = {
            'Language': Language,
            'Author': Author,
            'Book': Book,
            'Chapter': Chapter,
            'BookFile': BookFile,
            'ChangeLog': ChangeLog,
        }

        # Export order (dependencies first)
        export_order = ['Language', 'Author', 'Book', 'Chapter', 'BookFile', 'ChangeLog']
        
        # Filter to requested models while maintaining order
        models_to_export = [m for m in export_order if m in models_to_export]

        total_objects = 0
        all_exported_data = []
        
        for model_name in models_to_export:
            if model_name not in model_map:
                self.stdout.write(f"Warning: Unknown model '{model_name}'")
                continue

            model = model_map[model_name]
            objects = model.objects.all()
            count = objects.count()
            
            if count == 0:
                self.stdout.write(f"No {model_name} objects found, skipping...")
                continue

            # Serialize the data to JSON format directly
            serialized_data = serializers.serialize(
                'json', 
                objects, 
                indent=2,
                use_natural_foreign_keys=use_natural,
                use_natural_primary_keys=use_natural
            )
            
            # Parse the JSON data
            data = json.loads(serialized_data)
            
            # Remove file fields if requested
            if exclude_files:
                for item in data:
                    if 'fields' in item:
                        # Remove file/image fields
                        file_fields = ['cover_image', 'file']
                        for field in file_fields:
                            if field in item['fields']:
                                item['fields'][field] = ''

            # Write individual model file
            filename = f"{model_name.lower()}.json"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Add to combined data
            all_exported_data.extend(data)
            
            total_objects += count
            self.stdout.write(
                self.style.SUCCESS(f"Exported {count} {model_name} objects to {filepath}")
            )

        # Create a combined fixture
        if all_exported_data:
            combined_filepath = os.path.join(output_dir, 'books_complete.json')
            with open(combined_filepath, 'w', encoding='utf-8') as f:
                json.dump(all_exported_data, f, indent=2, ensure_ascii=False)
            
            self.stdout.write(
                self.style.SUCCESS(f"Created combined fixture: {combined_filepath}")
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nExport complete! Total objects exported: {total_objects}")
        )