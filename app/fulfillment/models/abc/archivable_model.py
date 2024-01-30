from django.db import models

__all__ = ["ArchivableModel"]


class ArchivableQueryset(models.QuerySet):
    def archived(self):
        return self.filter(is_archived=True)

    def non_archived(self):
        return self.filter(is_archived=False)


class ArchivableManager(models.Manager):
    def get_queryset(self):
        return ArchivableQueryset(self.model, using=self._db).all()

    def archived(self):
        return self.get_queryset().archived()

    def non_archived(self):
        return self.get_queryset().non_archived()


class ArchivableModel(models.Model):
    is_archived = models.BooleanField(default=False)

    archive_manager = ArchivableManager()
    objects = models.Manager()

    class Meta:
        abstract = True

    def already_archived(self):
        return self.is_archived

    def archive(self):
        self.is_archived = True

    def unarchive(self):
        self.is_archived = False
