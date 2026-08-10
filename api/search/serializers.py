from rest_framework import serializers

from .models import RecentSearch, SavedSearch, SearchHistory


class SavedSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedSearch
        fields = '__all__'
        read_only_fields = ('id', 'workspace', 'user', 'created_at', 'updated_at')


class RecentSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecentSearch
        fields = '__all__'
        read_only_fields = ('id', 'workspace', 'user', 'created_at', 'updated_at')


class SearchHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchHistory
        fields = '__all__'
        read_only_fields = ('id', 'workspace', 'user', 'created_at', 'updated_at')
