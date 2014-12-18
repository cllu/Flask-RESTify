
class Packable:
    """An interface that supports dump to json
    """

    def pack(self):
        """
        :rtype: dict
        """
        raise NotImplementedError
