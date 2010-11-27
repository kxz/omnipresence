from twisted.plugin import pluginPackagePaths

# Make twisted.plugin.getPlugins() look for plug-ins here.
__path__.extend(pluginPackagePaths(__name__))
__all__ = []
