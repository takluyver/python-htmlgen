import sys

try:
    from html import escape
except ImportError:
    from cgi import escape


class Generator(object):

    """Base class for HTML generators.

    Sub-classes must implement the generate() method, which returns an
    iterable containing strings and further generator objects. __iter__()
    flattens this iterator and returns a list of UTF-8 encoded byte strings:

        >>> class InnerGenerator(Generator):
        ...     def generate(self):
        ...         yield "XXX"
        >>> class OuterGenerator(Generator):
        ...     def generate(self):
        ...         yield "Foo"
        ...         yield InnerGenerator()
        >>> generator = OuterGenerator()
        >>> list(iter(generator))
        [b'Foo', b'XXX']

    __str__() returns a concatenated version of the strings returned by
    __iter__():

        >>> str(generator)
        'FooXXX'

    """

    def __iter__(self):
        """Return a flat iterator over the strings and generators returned
        by generate()."""
        self._iterator_stack = [self.generate()]
        while self._iterator_stack:
            iterator = self._iterator_stack[-1]
            try:
                item = next(iterator)
            except StopIteration:
                self._iterator_stack.pop()
            else:
                if hasattr(item, "generate"):
                    self._iterator_stack.append(item.generate())
                else:
                    if sys.version_info[0] <= 2 and isinstance(item, str):
                        yield item
                    else:
                        yield item.encode("utf-8")
        raise StopIteration()

    def __str__(self):
        """Return a concatenation of the strings returned by __iter__()."""
        return "".join(s.decode("utf-8") for s in self)

    def generate(self):
        """To be overridden by sub-classes. Return an iterator over strings
        and generator objects.

        """
        raise NotImplementedError()


class NullGenerator(Generator):

    """A generator that generates nothing."""

    def generate(self):
        return iter([])


class ChildGenerator(Generator):

    """A generator that generates children appended to it.

        >>> generator = ChildGenerator()
        >>> generator.append("String")
        >>> generator.extend(["Lis", "t"])
        >>> list(iter(generator))
        [b'String', b'Lis', b't']
        >>> sub_generator = ChildGenerator()
        >>> sub_generator.append("Sub")
        >>> generator.append(sub_generator)
        >>> list(iter(generator))
        [b'String', b'Lis', b't', b'Sub']

    """

    def __init__(self):
        super(ChildGenerator, self).__init__()
        self._children = []

    def __len__(self):
        """Return the number of children.

        This is not the number of items returned by __iter__.

        """
        return len(self._children)

    def append(self, child):
        """Append a string or sub generator."""
        self._children.append(child)

    def extend(self, children):
        """Append multiple strings and sub generators."""
        self._children.extend(children)

    def empty(self):
        """Remove all children."""
        self._children = []

    def generate(self):
        """Return an iterator over all children, in order.

        Sub-classes are encouraged to override or enhance this method,
        if desired.

        """
        return iter(self._children)


class HTMLChildGenerator(Generator):

    """A generator that handles HTML safely.

    HTMLChildGenerator works similar to ChildGenerator, but reserved HTML
    characters in strings appended with append() or extend() are
    escaped:

        >>> generator = HTMLChildGenerator()
        >>> generator.append("<Test>")
        >>> generator.extend(["x", "&", "y"])
        >>> list(iter(generator))
        [b'&lt;Test&gt;', b'x', b'&amp;', b'y']

    It is also possible to append strings without processing:

        >>> generator = HTMLChildGenerator()
        >>> generator.append_raw("<Test>")
        >>> generator.extend_raw(["x", "&", "y"])
        >>> list(iter(generator))
        [b'<Test>', b'x', b'&', b'y']

    Strings in sub-generators are not affected:

        >>> sub_generator = ChildGenerator()
        >>> sub_generator.append("<sub>")
        >>> generator = HTMLChildGenerator()
        >>> generator.extend(["<base>", sub_generator])
        >>> list(iter(generator))
        [b'&lt;base&gt;', b'<sub>']

    """

    def __init__(self):
        super(HTMLChildGenerator, self).__init__()
        self._children = ChildGenerator()

    def __len__(self):
        """Return the number of children.

        This is not the number of items returned by __iter__.

        """
        return len(self._children)

    def append(self, child):
        """Append a string or sub generator.

        Strings are escaped to be HTML-safe.

        """
        if not hasattr(child, "generate"):
            child = escape(child)
        self.append_raw(child)

    def append_raw(self, child):
        """Append a string or sub generator without escaping it.

        Strings are NOT escaped! Therefore, you should use this method only
        with HTML from trusted sources.

        """
        self._children.append(child)

    def extend(self, children):
        """Append multiple strings and sub generators.

        Strings are escaped to be HTML-safe.

        """
        for child in children:
            self.append(child)

    def extend_raw(self, children):
        """Append multiple strings and sub generators, without escaping them.

        Strings are NOT escaped! Therefore, you should use this method only
        with HTML from trusted sources.

        """
        for child in children:
            self.append_raw(child)

    def empty(self):
        """Remove all children."""
        self._children.empty()

    def generate(self):
        """Return an iterator over all children, in order.

        Sub-classes are encouraged to override or enhance this method,
        if desired.

        """
        return self._children.generate()


class JoinGenerator(ChildGenerator):

    """Generate the supplied pieces, separated by glue.

        >>> generator = JoinGenerator(", ", ["Hello", "World"])
        >>> list(iter(generator))
        [b'Hello', b', ', b'World']

    Pieces can be strings or sub-generators:

        >>> generator = JoinGenerator(", ", ["Hello"])
        >>> sub_generator = ChildGenerator()
        >>> sub_generator.append("World")
        >>> generator.append(sub_generator)
        >>> list(iter(generator))
        [b'Hello', b', ', b'World']

    """

    def __init__(self, glue, pieces=None):
        super(JoinGenerator, self).__init__()
        self._glue = glue
        if pieces:
            self.extend(pieces)

    def generate(self):
        pieces = super(JoinGenerator, self).generate()
        yield next(pieces)
        while True:
            piece = next(pieces)
            yield self._glue
            yield piece


class HTMLJoinGenerator(HTMLChildGenerator):

    """Generate the supplied pieces, separated by glue.

    This works like JoinGenerator, but reserved HTML characters in glue and
    string pieces are escaped. Sub-generators are not escaped:

        >>> generator = HTMLJoinGenerator(" & ", ["<Hello>"])
        >>> sub_generator = ChildGenerator()
        >>> sub_generator.append("<World>")
        >>> generator.append(sub_generator)
        >>> list(iter(generator))
        [b'&lt;Hello&gt;', b' &amp; ', b'<World>']

    """

    def __init__(self, glue, pieces=None):
        super(HTMLJoinGenerator, self).__init__()
        self._glue = escape(glue)
        if pieces:
            self.extend(pieces)

    def generate(self):
        pieces = super(HTMLJoinGenerator, self).generate()
        yield next(pieces)
        while True:
            piece = next(pieces)
            yield self._glue
            yield piece
