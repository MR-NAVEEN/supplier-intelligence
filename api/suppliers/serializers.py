from rest_framework import serializers

from .models import Supplier, SupplierAttachment, SupplierContact, SupplierNote


class SupplierContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierContact
        fields = '__all__'
        read_only_fields = ('id', 'supplier', 'created_at', 'updated_at')


class SupplierNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierNote
        fields = '__all__'
        read_only_fields = ('id', 'supplier', 'created_by', 'created_at', 'updated_at')


class SupplierAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierAttachment
        fields = '__all__'
        read_only_fields = ('id', 'supplier', 'uploaded_by', 'created_at', 'updated_at')


class SupplierSerializer(serializers.ModelSerializer):
    contacts_count = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = (
            'id', 'name', 'company_name', 'email', 'phone', 'website', 'address',
            'city', 'country', 'status', 'tags', 'ai_summary', 'metadata',
            'contacts_count', 'products_count', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'ai_summary', 'created_at', 'updated_at')

    def get_contacts_count(self, obj):
        return obj.contacts.count()

    def get_products_count(self, obj):
        return obj.products.count()
